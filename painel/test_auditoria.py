import json
import socket
from unittest.mock import patch

from testes_comum import HttpBase, app, lead, reinicia
from auditoria_cnpj import consultar
from auditoria_http import FalhaHTTP, destino
from auditoria_site import Pagina, cnpj_valido, tecnologias, whatsapp
from rotas_auditoria import fila


class AuditoriaHttp(HttpBase):
    def setUp(self):
        reinicia()
        app.leads['L1'] = lead(id='L1')

    def test_relatorio_disponivel_para_lead_existente(self):
        status, dados = self.req('/api/leads/L1/auditoria', token=app.API_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(dados['estado'], 'nao_executada')

    def test_cnpj_invalido_nao_dispara_consulta(self):
        status, _ = self.req('/api/leads/L1/auditoria', token=app.API_TOKEN,
                             metodo='POST', corpo={'cnpj': '00.000.000/0000-00'})
        self.assertEqual(status, 400)

    def test_evidencia_de_anuncio_precisa_vir_da_biblioteca(self):
        status, _ = self.req('/api/leads/L1/auditoria/anuncios', token=app.API_TOKEN,
                             metodo='POST', corpo={'plataforma': 'meta', 'estado': 'encontrado',
                                                    'url': 'https://exemplo.com/anuncio'})
        self.assertEqual(status, 400)

    def test_fila_persiste_relatorio_e_nao_inclui_no_listao(self):
        resultado = {'site': {'estado': 'sem_site'}, 'atualizado_em': 1}
        with patch('rotas_auditoria.auditar', return_value=resultado):
            status, _ = self.req('/api/leads/L1/auditoria', token=app.API_TOKEN, metodo='POST', corpo={})
            self.assertEqual(status, 202)
            fila.join()
        _, dados = self.req('/api/leads/L1/auditoria', token=app.API_TOKEN)
        self.assertEqual(dados['estado'], 'concluida')
        self.assertEqual(dados['relatorio'], resultado)
        _, lista = self.req('/api/leads', token=app.API_TOKEN)
        self.assertNotIn('auditoria', lista[0])

    def test_cadastro_e_tags_separam_empresa_socio_e_anuncios(self):
        site = Pagina("""<footer>CNPJ 00.000.000/0001-91</footer>
            <a href="https://wa.me/5511999999999">WhatsApp</a>
            <a href="tel:+551133334455" aria-label="Ana Teste">Ligar</a>
            <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
            <script>gtag('config', 'AW-123456789');</script>
            <script type="application/ld+json">{"@type":"Person","name":"Ana Teste",
              "telephone":"11 3333-4444","email":"ana@empresa.example"}</script>""",
            'https://empresa.example/')
        dados = {'cnpj': '00000000000191', 'nome_fantasia': 'Empresa Teste', 'municipio': 'São Paulo',
                 'uf': 'SP', 'ddd_telefone_1': '1133330000', 'qsa': [
                     {'nome_socio': 'Ana Teste', 'qualificacao_socio': 'Sócia', 'cnpj_cpf_do_socio': 'omitido'},
                     {'nome_socio': 'João Teste', 'qualificacao_socio': 'Sócio'}]}
        mock = {'status': 200, 'texto': json.dumps(dados)}
        empresa = {'nome': 'Empresa Teste', 'cidade': 'São Paulo', 'uf': 'SP'}
        with patch('auditoria_cnpj.obter', return_value=mock):
            c = consultar(empresa, [site])
            self.assertEqual(consultar({**empresa, 'cidade': 'Santos'}, [site])['estado'], 'revisar')
        self.assertEqual(c['estado'], 'identificado')
        self.assertEqual(c['socios'][0]['contatos'][0]['email'], 'ana@empresa.example')
        self.assertEqual(c['socios'][0]['contatos'][1]['telefone'], '551133334455')
        self.assertEqual(c['socios'][1]['contatos'], [])
        self.assertNotIn('cnpj_cpf_do_socio', c['socios'][0])
        self.assertEqual({x['nome'] for x in tecnologias([site])}, {'Meta Pixel', 'Google Ads'})
        self.assertEqual(whatsapp([site])['url'], 'https://wa.me/5511999999999')

    def test_validacao_e_rede_publica(self):
        self.assertEqual(cnpj_valido('00.000.000/E08G-12'), '00000000E08G12')
        dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
        with patch('auditoria_http.socket.getaddrinfo', return_value=dns):
            with self.assertRaises(FalhaHTTP):
                destino('https://empresa.example/')
