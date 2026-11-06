"""Cliente restrito ao motor SITH.IA local. Nunca recebe URLs ou credenciais do navegador."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
import normaliza
from estado import buscas, lock
from exclusao_buscas import job_excluido

LIMITE_RESPOSTA = 20 * 1024 * 1024
QUANTIDADES = {20: (2, 600), 60: (5, 1200), 120: (10, 1800), 200: (18, 3600)}


class ScraperError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def base_url():
    value = os.environ.get('SITH_SCRAPER_URL', 'http://127.0.0.1:8081')
    try:
        url = urllib.parse.urlsplit(value)
        port = url.port
        if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1')
                or not port or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment):
            raise ValueError()
    except ValueError:
        raise ScraperError(503, 'O endereço do scraper precisa ser uma porta local válida.') from None
    host = '[::1]' if url.hostname == '::1' else '127.0.0.1'
    return f'http://{host}:{port}'


def job_id(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise ScraperError(400, 'Identificador de busca inválido.') from None


def request(method, path, body=None):
    data = json.dumps(body, allow_nan=False).encode() if body is not None else None
    req = urllib.request.Request(base_url() + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'SITH.IA-Prospecta/1.0'})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), SemRedirect())
        with opener.open(req, timeout=15) as response:
            raw = response.read(LIMITE_RESPOSTA + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ScraperError(404, 'Busca ou resultado não encontrado no scraper.') from None
        raise ScraperError(502, 'O scraper recusou a operação. Atualize e tente novamente.') from None
    except (OSError, urllib.error.URLError):
        raise ScraperError(503, 'Scraper desligado. Abra a Prospecta SITH.IA para ligar o motor.') from None
    if len(raw) > LIMITE_RESPOSTA:
        raise ScraperError(502, 'Resultado grande demais para importar de uma vez.')
    return raw


def request_json(method, path, body=None):
    try:
        return json.loads(request(method, path, body))
    except (ValueError, UnicodeError):
        raise ScraperError(502, 'O scraper devolveu uma resposta inválida.') from None


def get_job(value):
    jid = job_id(value)
    if job_excluido(jid):
        raise ScraperError(410, 'Essa busca foi excluída com seus leads no CRM.')
    result = request_json('GET', f'/api/v1/jobs/{jid}')
    if not isinstance(result, dict) or job_id(result.get('ID')) != jid:
        raise ScraperError(502, 'A busca devolvida pelo scraper não corresponde à solicitada.')
    return result


def busca_do_job(jid):
    return next((b for b in buscas.values() if b.get('scraper_job_id') == jid or jid in b.get('jobs_motor', [])), None)


def listar():
    jobs = request_json('GET', '/api/v1/jobs') or []
    if not isinstance(jobs, list):
        raise ScraperError(502, 'A lista de buscas do scraper está inválida.')
    result = []
    with lock:
        for job in jobs[:1000]:
            if not isinstance(job, dict):
                continue
            try:
                jid = job_id(job.get('ID'))
            except ScraperError:
                continue
            local = busca_do_job(jid)
            if job_excluido(jid):
                continue
            data = job.get('Data') if isinstance(job.get('Data'), dict) else {}
            result.append({'id': jid, 'nome': str(job.get('Name') or 'Busca sem nome')[:200],
                           'status': str(job.get('Status') or 'pending')[:30], 'criado_em': job.get('CreatedAt'),
                           'lat': data.get('Lat'), 'lon': data.get('Lon'), 'raio': data.get('Radius'),
                           'busca_id': local['id'] if local else None,
                           'na_lixeira': bool(local and local.get('lixeira_em')),
                           'importado': bool(local and not local.get('lixeira_em') and local.get('estado') == 'concluida')})
    result.sort(key=lambda j: str(j.get('criado_em') or ''), reverse=True)
    return {'conectado': True, 'jobs': result}


def criar(data):
    if not isinstance(data, dict):
        raise ScraperError(400, 'Informe os parâmetros da busca.')
    nichos, local = data.get('nichos'), data.get('local')
    quantidade, raio = data.get('quantidade', 60), data.get('raio', 5)
    idioma, emails, tempo = data.get('idioma', 'pt'), data.get('emails', False), data.get('tempo', 'auto')
    if not isinstance(nichos, str) or not 2 <= len(nichos.strip()) <= 300:
        raise ScraperError(400, 'Informe um nicho com até 300 caracteres.')
    terms = [n.strip() for n in nichos.split(',') if n.strip()]
    if not 1 <= len(terms) <= 10 or not isinstance(local, str) or not 3 <= len(local.strip()) <= 200:
        raise ScraperError(400, 'Informe até dez nichos e o bairro/cidade da busca.')
    if type(quantidade) is not int or quantidade not in QUANTIDADES or type(raio) is not int or not 1 <= raio <= 30:
        raise ScraperError(400, 'Quantidade ou raio de busca inválido.')
    if idioma not in ('pt', 'en', 'es') or type(emails) is not bool or str(tempo) not in ('auto', '600', '1200', '2400', '3600'):
        raise ScraperError(400, 'Idioma, e-mails ou tempo de busca inválido.')
    geo = normaliza.geocodificar(local.strip())
    if not geo:
        raise ScraperError(400, 'Não encontrei esse local. Informe bairro, cidade e estado.')
    depth, default_time = QUANTIDADES[quantidade]
    max_time = default_time * (2 if emails else 1) if tempo == 'auto' else int(tempo)
    body = {'name': ', '.join(terms)[:120] + ' · ' + local.strip()[:70],
            'keywords': [f'{term} em {local.strip()}' for term in terms], 'lang': idioma,
            'zoom': 16 if raio <= 1 else 15 if raio <= 3 else 14 if raio <= 7 else 13 if raio <= 15 else 12,
            'radius': raio * 1000, 'depth': depth, 'email': emails, 'max_time': max_time,
            'lat': str(geo[0]), 'lon': str(geo[1]), 'fast_mode': False}
    result = request_json('POST', '/api/v1/jobs', body)
    if not isinstance(result, dict):
        raise ScraperError(502, 'O scraper não confirmou a criação da busca.')
    return {'id': job_id(result.get('id')), 'lat': geo[0], 'lon': geo[1], 'raio': raio * 1000}
