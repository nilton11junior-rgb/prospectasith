"""Exclusão explícita e em lote limpa as referências do CRM, inclusive leads compartilhados."""
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from testes_comum import HttpBase, TMP, app, lead, reinicia


def semear():
    reinicia()
    for bid in ('b1', 'b2', 'b3'):
        app.buscas[bid] = {'id': bid, 'estado': 'erro' if bid == 'b1' else 'concluida',
            'etapa': 'Teste', 'criado_em': time.time(), 'jobs_motor': [], 'avisos': [],
            'parametros': {'nichos': ['Teste'], 'cidade': 'Guarujá', 'uf': 'SP', 'tamanho': 'rapida'},
            'lead_ids': {'b1': ['novo', 'trab', 'comum'], 'b2': ['comum', 'outro'], 'b3': []}[bid]}
    app.leads.update(novo=lead(id='novo', buscas=['b1']),
                     trab=lead(id='trab', buscas=['b1'], status='reuniao', obs='Nota de teste'),
                     comum=lead(id='comum', buscas=['b1', 'b2']), outro=lead(id='outro', buscas=['b2']))
    app.conversas.update(alvo={'lead_id': 'trab', 'numero': 'alvo', 'msgs': []},
                         outro={'lead_id': 'outro', 'numero': 'outro', 'msgs': []})
    app.agenda_dados['reservas'] = [{'id': 'r1', 'lead_id': 'trab'}, {'id': 'r2', 'lead_id': 'outro'}]
    app.pendentes_ia.update(alvo=100, outro=100)
    app.config['auto_envio'].update(ativo=True, buscas=['b1'])
    app.salvar_leads(); app.salvar_config()
    for b in app.buscas.values():
        app.salvar_busca(b)


class ExclusaoHttp(HttpBase):
    def setUp(self):
        semear()

    def test_excluir_um_lead_limpa_vinculos_e_preserva_buscas(self):
        app.buscas['b2']['lead_ids'].append('trab')
        app.buscas['b3']['lixeira_leads'] = {'trab': app.leads['trab']}
        self.assertEqual(self.req('/api/leads/trab', metodo='DELETE', token=app.API_TOKEN)[0], 200)
        self.assertEqual(set(app.buscas), {'b1', 'b2', 'b3'})
        self.assertEqual(set(app.leads), {'novo', 'comum', 'outro'})
        self.assertEqual(app.buscas['b1']['lead_ids'], ['novo', 'comum'])
        self.assertEqual(app.buscas['b2']['lead_ids'], ['comum', 'outro'])
        self.assertEqual(app.buscas['b3']['lixeira_leads'], {})
        self.assertEqual(set(app.conversas), {'outro'})
        self.assertEqual(set(app.pendentes_ia), {'outro'})
        self.assertEqual(app.agenda_dados['reservas'], [{'id': 'r2', 'lead_id': 'outro'}])
        self.assertTrue(app.config['auto_envio']['ativo'])
        app.leads.clear()
        app.buscas.clear()
        app.carregar()
        self.assertNotIn('trab', app.leads)
        self.assertNotIn('trab', app.buscas['b1']['lead_ids'])

    def test_operacoes_atrasadas_nao_recriam_vinculos_de_lead_excluido(self):
        from agenda import reservar
        from whatsapp import conversa_de

        antigo = app.leads['trab']
        self.assertEqual(self.req('/api/leads/trab', metodo='DELETE', token=app.API_TOKEN)[0], 200)
        with self.assertRaisesRegex(ValueError, 'Lead excluído'):
            conversa_de('alvo', antigo)
        inicio = '2027-01-04 10:00'
        with patch('agenda.slots_do_dia', return_value=[inicio]):
            with self.assertRaisesRegex(ValueError, 'Lead excluído'):
                reservar(antigo, inicio)

    def j(self, path, body):
        return self.req(path, token=app.API_TOKEN, metodo='POST', corpo=body)

    def preview(self, ids):
        code, data = self.j('/api/buscas/exclusao/previa', {'ids': ids})
        self.assertEqual(code, 200)
        return data

    def excluir(self, ids, preview=None):
        data = preview or self.preview(ids)
        return self.j('/api/buscas/exclusao', {'ids': ids, 'confirmacao': data['confirmacao']})

    def test_resumo_conta_compartilhados_trabalhados_e_vinculos(self):
        data = self.preview(['b1'])
        self.assertEqual({k: data[k] for k in ('buscas', 'leads', 'compartilhados', 'trabalhados', 'conversas', 'reservas')},
                         dict(buscas=1, leads=3, compartilhados=1, trabalhados=1, conversas=1, reservas=1))
        self.assertEqual(len(app.leads), 4)

    def test_cascata_remove_lead_de_todas_as_areas_e_preserva_outros(self):
        code, data = self.excluir(['b1'])
        self.assertEqual(code, 200)
        self.assertNotIn('b1', app.buscas)
        self.assertEqual(set(app.leads), {'outro'})
        self.assertEqual(app.buscas['b2']['lead_ids'], ['outro'])
        self.assertEqual(set(app.conversas), {'outro'})
        self.assertEqual(set(app.pendentes_ia), {'outro'})
        self.assertEqual(app.agenda_dados['reservas'], [{'id': 'r2', 'lead_id': 'outro'}])
        self.assertFalse(app.config['auto_envio']['ativo'])  # não transformar filtro vazio em envio para todos
        self.assertEqual(app.config['auto_envio']['buscas'], [])
        self.assertFalse(os.path.exists(os.path.join(app.DIR_BUSCAS, 'b1.json')))
        self.assertEqual(set(json.loads(Path(app.ARQ_LEADS).read_text(encoding='utf-8'))), {'outro'})
        self.assertTrue(data['backup'])

    def test_lote_deduplica_leads_e_apaga_todas_as_buscas_pedidas(self):
        p = self.preview(['b1', 'b2', 'b1'])
        self.assertEqual((p['buscas'], p['leads']), (2, 4))
        self.assertEqual(self.excluir(['b1', 'b2'], p)[0], 200)
        self.assertEqual(set(app.buscas), {'b3'})
        self.assertEqual(app.leads, {})

    def test_nao_aceita_selecao_vazia_ids_invalidos_ou_inexistentes(self):
        for ids in ([], ['../config'], ['b1', 'inexistente'], 'b1'):
            self.assertIn(self.j('/api/buscas/exclusao/previa', {'ids': ids})[0], (400, 404))
        self.assertEqual(set(app.buscas), {'b1', 'b2', 'b3'})

    def test_nao_exclui_sem_confirmacao_ou_se_resumo_mudou(self):
        self.assertEqual(self.j('/api/buscas/exclusao', {'ids': ['b1']})[0], 409)
        p = self.preview(['b1'])
        app.leads['extra'] = lead(id='extra', buscas=['b1'])
        self.assertEqual(self.excluir(['b1'], p)[0], 409)
        self.assertIn('b1', app.buscas)

    def test_nao_exclui_busca_ativa_nem_parte_de_lote_invalido(self):
        app.buscas['b2']['estado'] = 'rodando'
        self.assertEqual(self.j('/api/buscas/exclusao/previa', {'ids': ['b1', 'b2']})[0], 409)
        self.assertIn('b1', app.buscas)

    def test_progresso_de_outra_busca_nao_invalida_confirmacao(self):
        p = self.preview(['b1'])
        app.buscas['b3'].update(estado='rodando', etapa='Progresso de outra busca')
        self.assertEqual(self.excluir(['b1'], p)[0], 200)

    def test_trabalhador_e_edicao_de_outro_lead_continuam_atualizando_apos_exclusao(self):
        outra_busca, outro_lead = app.buscas['b3'], app.leads['outro']
        self.assertEqual(self.excluir(['b1'])[0], 200)
        outra_busca['etapa'] = 'Atualização do trabalhador ainda em execução'
        outro_lead['obs'] = 'Nova anotação da conversa em andamento'
        self.assertEqual(app.buscas['b3']['etapa'], outra_busca['etapa'])
        self.assertEqual(app.leads['outro']['obs'], outro_lead['obs'])

    def test_remove_copias_na_lixeira_para_nao_ressuscitar_lead(self):
        app.buscas['b2'].update(lixeira_em=time.time(), lixeira_leads={'comum': app.leads['comum']})
        self.assertEqual(self.excluir(['b1'])[0], 200)
        self.assertNotIn('comum', app.buscas['b2']['lixeira_leads'])

    def test_backup_falhando_nao_apaga_nada(self):
        p = self.preview(['b1'])
        with patch('exclusao_buscas.backup', side_effect=OSError('disco cheio')):
            self.assertEqual(self.excluir(['b1'], p)[0], 503)
        self.assertEqual(len(app.leads), 4)
        self.assertIn('b1', app.buscas)

    def test_dados_excluidos_nao_voltam_ao_recarregar(self):
        self.assertEqual(self.excluir(['b1'])[0], 200)
        app.buscas.clear(); app.leads.clear(); app.conversas.clear(); app.agenda_dados.clear()
        app.carregar()
        self.assertEqual(set(app.leads), {'outro'})
        self.assertNotIn('b1', app.buscas)

    def test_gravacao_atrasada_do_trabalhador_nao_recria_busca_apagada(self):
        antiga = app.buscas['b1']
        self.assertEqual(self.excluir(['b1'])[0], 200)
        app.salvar_busca(antiga)
        self.assertFalse(Path(app.DIR_BUSCAS, 'b1.json').exists())

    def test_api_sem_login_recusa_exclusao(self):
        self.assertIn(self.req('/api/buscas/exclusao', metodo='POST', corpo={'ids': ['b1']})[0], (401, 403))

    def test_limpa_conversa_e_reserva_orfas_mesmo_sem_lead_na_base(self):
        app.buscas['b1']['lead_ids'].append('ausente')
        app.conversas['orfao'] = {'lead_id': 'ausente', 'numero': 'orfao', 'msgs': []}
        app.agenda_dados['reservas'].append({'id': 'r3', 'lead_id': 'ausente'})
        self.assertEqual(self.excluir(['b1'])[0], 200)
        self.assertNotIn('orfao', app.conversas)
        self.assertFalse(any(r['lead_id'] == 'ausente' for r in app.agenda_dados['reservas']))

    def test_erro_de_gravacao_restaura_estado_e_arquivos(self):
        import exclusao_buscas
        gravar = exclusao_buscas._grava
        falhou = []
        def disco(caminho, objeto):
            if caminho == app.ARQ_AGENDA and not falhou:
                falhou.append(True)
                raise OSError('falha simulada')
            return gravar(caminho, objeto)
        p = self.preview(['b1'])
        with patch('exclusao_buscas._grava', side_effect=disco):
            self.assertEqual(self.excluir(['b1'], p)[0], 503)
        self.assertEqual(len(app.leads), 4)
        self.assertEqual(len(json.loads(Path(app.ARQ_LEADS).read_text(encoding='utf-8'))), 4)
        self.assertTrue(Path(app.DIR_BUSCAS, 'b1.json').exists())

    def test_scraper_excluido_fica_bloqueado_antes_da_limpeza_remota(self):
        import exclusao_buscas
        import scraper_motor
        jid = '11111111-1111-4111-8111-111111111111'
        app.buscas['b1']['scraper_job_id'] = jid
        code, data = self.excluir(['b1'])
        self.assertEqual(code, 200)
        self.assertEqual(data['limpeza_pendente'], 1)
        self.assertTrue(exclusao_buscas.job_excluido(jid))
        with self.assertRaises(scraper_motor.ScraperError) as erro:
            scraper_motor.get_job(jid)
        self.assertEqual(erro.exception.status, 410)
        with patch('scraper_motor.request', return_value=b''):
            exclusao_buscas.limpar_pendentes()
        self.assertTrue(exclusao_buscas.job_excluido(jid))
        self.assertFalse(json.loads(Path(exclusao_buscas.ARQ_EXCLUSOES).read_text(encoding='utf-8'))['scraper:' + jid]['pendente'])
