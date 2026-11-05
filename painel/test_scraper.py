"""Contratos reais HTTP e persistência da integração, usando motor local sintético."""
import copy
import csv
import io
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from testes_comum import HttpBase, app, lead, lixeira, reinicia

JOB = '11111111-1111-4111-8111-111111111111'
BUSCA = 'sith_11111111111141118111111111111111'
JOB_DATA = {'ID': JOB, 'Name': 'Dentistas · Guarujá', 'Status': 'ok',
            'CreatedAt': '2026-11-05T03:00:00Z',
            'Data': {'Keywords': ['dentistas em Guarujá, SP'], 'Lat': '-23.99', 'Lon': '-46.25', 'Radius': 5000}}
ROWS = [
    {'place_id': 'ChIJTESTE1', 'title': 'Clínica Mapa', 'phone': '(13) 98888-7777',
     'website': 'https://instagram.com/clinica', 'emails': 'contato@example.test',
     'address': 'Rua Um, Centro - Guarujá - SP', 'category': 'Dentista', 'review_rating': '4.8', 'review_count': '42',
     'latitude': '-23.99', 'longitude': '-46.25', 'link': 'https://maps.google.com/?cid=111',
     'complete_address': json.dumps({'borough': 'Centro', 'city': 'Guarujá', 'state': 'SP'})},
    {'place_id': 'ChIJTESTE2', 'title': 'Clínica Sem Coordenadas', 'phone': '(13) 3333-4444',
     'address': 'Rua Dois, Guarujá - SP', 'category': 'Dentista', 'review_rating': '4.5', 'review_count': '20',
     'complete_address': json.dumps({'city': 'Guarujá', 'state': 'SP'})},
]


def csv_bytes(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(ROWS[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


class MotorFake(BaseHTTPRequestHandler):
    job = copy.deepcopy(JOB_DATA)
    rows = copy.deepcopy(ROWS)
    raw = None
    redirect = False
    posted = None

    def log_message(self, *args):
        pass

    def reply(self, status, value, tipo='application/json'):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.redirect:
            self.send_response(302)
            self.send_header('Location', 'http://127.0.0.1:1/nao-acessar')
            self.end_headers()
        elif self.path == '/api/v1/jobs':
            self.reply(200, [self.job])
        elif self.path == f'/api/v1/jobs/{JOB}':
            self.reply(200, self.job)
        elif self.path == f'/api/v1/jobs/{JOB}/download':
            self.reply(200, self.raw if self.raw is not None else csv_bytes(self.rows), 'text/csv')
        else:
            self.reply(404, {'message': 'job not found'})

    def do_POST(self):
        type(self).posted = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.reply(201, {'id': JOB})


class ScraperHTTP(HttpBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.motor = ThreadingHTTPServer(('127.0.0.1', 0), MotorFake)
        cls.old_url = os.environ.get('SITH_SCRAPER_URL')
        os.environ['SITH_SCRAPER_URL'] = f'http://127.0.0.1:{cls.motor.server_address[1]}'
        threading.Thread(target=cls.motor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.motor.shutdown()
        cls.motor.server_close()
        if cls.old_url is None:
            os.environ.pop('SITH_SCRAPER_URL', None)
        else:
            os.environ['SITH_SCRAPER_URL'] = cls.old_url
        super().tearDownClass()

    def setUp(self):
        reinicia()
        MotorFake.job, MotorFake.rows = copy.deepcopy(JOB_DATA), copy.deepcopy(ROWS)
        MotorFake.raw, MotorFake.redirect, MotorFake.posted = None, False, None

    def importar(self, job=JOB):
        return self.req(f'/api/scraper/jobs/{job}/importar', app.API_TOKEN, 'POST', {})

    def test_lista_exige_login(self):
        self.assertEqual(self.req('/api/scraper/jobs')[0], 401)
        status, data = self.req('/api/scraper/jobs', app.API_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(data['jobs'][0]['id'], JOB)
        self.assertEqual(data['jobs'][0]['status'], 'ok')

    def test_importa_csv_completo_inclusive_sem_coordenadas(self):
        status, data = self.importar()
        self.assertEqual(status, 200)
        self.assertEqual((data['novos'], data['total']), (2, 2))
        self.assertEqual(set(app.leads), {'ChIJTESTE1', 'ChIJTESTE2'})
        self.assertEqual(app.leads['ChIJTESTE1']['whatsapp'], '5513988887777')
        self.assertEqual(app.leads['ChIJTESTE1']['instagram'], 'https://instagram.com/clinica')
        self.assertEqual(app.buscas[BUSCA]['origem'], 'sithia_scraper')
        self.assertEqual(app._le(app.ARQ_LEADS, {})['ChIJTESTE2']['nome'], 'Clínica Sem Coordenadas')

    def test_reimportacao_preserva_comercial_e_nao_duplica(self):
        app.leads['ChIJTESTE1'] = lead(id='ChIJTESTE1', status='reuniao', obs='Cliente prefere à tarde', optout=True)
        history = copy.deepcopy(app.leads['ChIJTESTE1']['historico'])
        self.assertEqual(self.importar()[0], 200)
        status, data = self.importar()
        self.assertEqual((status, data['novos'], len(app.leads), len(app.buscas)), (200, 0, 2, 1))
        existing = app.leads['ChIJTESTE1']
        self.assertEqual((existing['status'], existing['obs'], existing['optout']), ('reuniao', 'Cliente prefere à tarde', True))
        self.assertEqual(existing['historico'], history)
        self.assertEqual(existing['buscas'].count(BUSCA), 1)
        self.assertEqual(len(app.leads['ChIJTESTE2']['historico']), 1)

    def test_lixeira_nao_reaparece_por_importacao(self):
        self.assertEqual(self.importar()[0], 200)
        lixeira.mandar(BUSCA, 'Fora do foco')
        self.assertEqual(self.importar()[0], 409)
        self.assertEqual(app.leads, {})
        self.assertTrue(app.buscas[BUSCA]['lixeira_em'])

    def test_nao_importa_job_em_execucao(self):
        MotorFake.job['Status'] = 'working'
        self.assertEqual(self.importar()[0], 409)
        self.assertEqual(app.leads, {})

    def test_uuid_invalido_nao_cria_dados(self):
        self.assertEqual(self.importar('nao-e-uuid')[0], 400)
        self.assertEqual(app.leads, {})

    def test_csv_invalido_nao_muda_base(self):
        MotorFake.raw = b'campo_errado\nvalor\n'
        self.assertEqual(self.importar()[0], 502)
        self.assertEqual(app.leads, {})
        self.assertEqual(app.buscas, {})

    def test_motor_nao_redireciona(self):
        MotorFake.redirect = True
        self.assertEqual(self.importar()[0], 502)
        self.assertEqual(app.leads, {})

    def test_resultados_mapa_preservam_empresas_sem_latitude(self):
        status, data = self.req(f'/api/scraper/jobs/{JOB}/resultados', app.API_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual((data['total'], len(data['empresas'])), (2, 2))
        self.assertEqual(data['empresas'][0]['latitude'], -23.99)
        self.assertIsNone(data['empresas'][1]['latitude'])
        self.assertEqual(data['empresas'][1]['id'], 'ChIJTESTE2')

    def test_busca_ja_feita_pelo_crm_nao_duplica_historico_de_buscas(self):
        app.buscas['bexistente'] = {'id': 'bexistente', 'estado': 'concluida', 'parametros': {'nichos': ['dentistas'],
                                  'cidade': 'Guarujá', 'uf': 'SP'}, 'lead_ids': [], 'jobs_motor': [JOB], 'criado_em': 1}
        status, data = self.importar()
        self.assertEqual(status, 200)
        self.assertEqual(data['busca_id'], 'bexistente')
        self.assertEqual(len(app.buscas), 1)

    def test_importacao_nao_altera_automacoes_ou_conversas(self):
        config = copy.deepcopy(app.config)
        app.conversas['5513988887777'] = {'lead_id': 'ChIJTESTE1', 'msgs': [{'de': 'lead', 'txt': 'Olá'}]}
        conversas = copy.deepcopy(app.conversas)
        self.assertEqual(self.importar()[0], 200)
        self.assertEqual(app.config, config)
        self.assertEqual(app.conversas, conversas)

    def test_cria_job_com_contrato_do_motor(self):
        with patch('normaliza.geocodificar', return_value=('-23.99', '-46.25', [])):
            status, data = self.req('/api/scraper/jobs', app.API_TOKEN, 'POST',
                                    {'nichos': 'dentistas, clínicas', 'local': 'Guarujá, SP', 'quantidade': 60,
                                     'raio': 5, 'idioma': 'pt', 'emails': True, 'tempo': 'auto'})
        self.assertEqual(status, 201)
        self.assertEqual(data['id'], JOB)
        self.assertEqual(MotorFake.posted['keywords'], ['dentistas em Guarujá, SP', 'clínicas em Guarujá, SP'])
        self.assertEqual((MotorFake.posted['depth'], MotorFake.posted['radius'], MotorFake.posted['max_time']), (5, 5000, 2400))
        self.assertEqual((MotorFake.posted['lat'], MotorFake.posted['lon']), ('-23.99', '-46.25'))

    def test_parametro_invalido_e_recusado_antes_de_buscar(self):
        status, _ = self.req('/api/scraper/jobs', app.API_TOKEN, 'POST', {'nichos': 'x', 'local': '', 'raio': -1})
        self.assertEqual(status, 400)
        self.assertIsNone(MotorFake.posted)

    def test_busca_importada_nao_entra_na_fila_do_motor_antigo(self):
        self.assertEqual(self.importar()[0], 200)
        status, _ = self.req(f'/api/buscas/{BUSCA}/repetir', app.API_TOKEN, 'POST', {})
        self.assertEqual(status, 409)
        self.assertEqual(app.fila, [])


if __name__ == '__main__':
    unittest.main()
