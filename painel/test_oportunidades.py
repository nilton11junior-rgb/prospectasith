from testes_comum import HttpBase, app, lead, reinicia
from unittest.mock import patch

from rotas_auditoria import fila, programar_automaticas


class OportunidadesHttp(HttpBase):
    def setUp(self):
        reinicia()
        app.leads['site'] = lead(id='site', site='https://empresa.example', whatsapp='551133334444')
        app.leads['site']['auditoria'] = {'relatorio': {
            'site': {'estado': 'respondendo'},
            'whatsapp': {'estado': 'erro_http', 'status': 404},
            'tags': [],
        }}
        app.leads['optout'] = lead(id='optout', optout=True)
        app.leads['fechado'] = lead(id='fechado', status='fechado')

    def test_lista_prioriza_problema_real_e_exclui_leads_fora_da_prospeccao(self):
        status, dados = self.req('/api/oportunidades', token=app.API_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual([x['id'] for x in dados['itens']], ['site'])
        item = dados['itens'][0]
        self.assertEqual(item['grupo'], 'conversao')
        self.assertEqual(item['prioridade'], 'priorizar')
        self.assertIn('404', ' '.join(item['evidencias']))
        self.assertEqual(item['abordagem'].count('?'), 1)
        self.assertNotIn('http', item['abordagem'])

    def test_auditoria_automatica_processa_novos_e_pula_os_outros(self):
        app.leads['novo'] = lead(id='novo', nome='Empresa Nova')
        with patch('rotas_auditoria.auditar', return_value={'site': {'estado': 'sem_site'}}) as executar:
            resultado = programar_automaticas()
            self.assertEqual(resultado['na_fila'], 1)
            fila.join()
        self.assertEqual(executar.call_count, 1)
        self.assertEqual(executar.call_args.args[0]['nome'], 'Empresa Nova')
        _, dados = self.req('/api/leads/novo/auditoria', token=app.API_TOKEN)
        self.assertEqual(dados['estado'], 'concluida')
        self.assertNotIn('auditoria', app.leads['optout'])

    def test_lead_em_conversa_tem_proximo_passo_sem_rascunho_inicial(self):
        app.leads['site']['status'] = 'respondeu'
        _, dados = self.req('/api/leads/site/oportunidade', token=app.API_TOKEN)
        item = dados['item']
        self.assertEqual(item['prioridade'], 'responder')
        self.assertEqual(item['abordagem'], '')
        if item['segmento']:
            _, filtrada = self.req('/api/oportunidades?segmento=' + item['segmento'], token=app.API_TOKEN)
            self.assertEqual(filtrada['total'], 1)
