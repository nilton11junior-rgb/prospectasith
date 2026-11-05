"""CSV completo do SITH.IA -> mapa e base única do CRM, sem tocar no estado comercial."""
import csv
import io
import json
import math
import re
import time
import urllib.parse
from estado import CAMPOS_CONTATO, buscas, leads, lock, salvar_busca, salvar_leads
from normaliza import lead_de, mesclar_leads, whatsapp_em
from scraper_motor import ScraperError, busca_do_job, get_job, job_id, request

csv.field_size_limit(20 * 1024 * 1024)


def coordenada(value, limite):
    try:
        value = float(value)
        return value if math.isfinite(value) and -limite <= value <= limite else None
    except (ValueError, TypeError):
        return None


def normalizar(row):
    row = {k: str(v or '')[:10000] for k, v in row.items()}
    if not re.fullmatch(r'[\w-]{1,200}', row.get('place_id', ''), flags=re.ASCII):
        row['place_id'] = ''
    try:
        address = json.loads(row.get('complete_address') or '{}')
    except ValueError:
        address = {}
    if not isinstance(address, dict):
        address = {}
    row['complete_address'] = json.dumps({k: str(v or '')[:500] for k, v in address.items()})
    result = lead_de(row)
    if not math.isfinite(result['nota']):
        result['nota'] = 0.0
    result['avaliacoes'] = max(0, result['avaliacoes'])
    host = (urllib.parse.urlsplit(result['site'] if '://' in result['site'] else 'https://' + result['site']).hostname or '').lower()
    for domain, field in (('instagram.com', 'instagram'), ('facebook.com', 'facebook'), ('linkedin.com', 'linkedin')):
        if host == domain or host.endswith('.' + domain):
            result[field] = result['site']
    wa = whatsapp_em(result['site'])
    if wa:
        result['whatsapp'], result['whatsapp_origem'] = wa, 'site'
    result['latitude'], result['longitude'] = coordenada(row.get('latitude'), 90), coordenada(row.get('longitude'), 180)
    return result


def ler_resultados(job):
    jid = job_id(job['ID'])
    try:
        raw = request('GET', f'/api/v1/jobs/{jid}/download')
    except ScraperError as error:
        if error.status == 404 and job.get('Status') in ('pending', 'working'):
            return []
        raise
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
        fields = reader.fieldnames or []
        if not {'title', 'address'}.issubset(fields) or len(set(fields)) != len(fields):
            raise ValueError('CSV sem cabeçalho esperado')
        result, seen = [], set()
        for count, row in enumerate(reader, 1):
            if count > 20000 or None in row:
                raise ValueError('CSV fora dos limites')
            if not row.get('title', '').strip():
                continue
            empresa = normalizar(row)
            if empresa['id'] not in seen:
                result.append(empresa)
                seen.add(empresa['id'])
        return result
    except (UnicodeError, csv.Error, ValueError, TypeError, OverflowError):
        raise ScraperError(502, 'O resultado do scraper está em formato inválido. Nenhum lead foi importado.') from None


def resultados(value):
    job = get_job(value)
    empresas = ler_resultados(job)
    return {'id': job['ID'], 'status': job.get('Status'), 'total': len(empresas), 'empresas': empresas}


def importar(value):
    job = get_job(value)
    jid = job_id(job['ID'])
    if job.get('Status') != 'ok':
        raise ScraperError(409, 'Aguarde a busca concluir antes de importar para o CRM.')
    empresas = ler_resultados(job)
    with lock:
        previous = busca_do_job(jid)
        if previous and previous.get('lixeira_em'):
            raise ScraperError(409, 'Essa busca está na lixeira do CRM. Restaure-a antes de importar novamente.')
        if previous and previous.get('estado') in ('rodando', 'na_fila'):
            raise ScraperError(409, 'Essa busca ainda está sendo organizada pelo CRM. Aguarde a conclusão.')
        now = time.time()
        data = job.get('Data') if isinstance(job.get('Data'), dict) else {}
        keywords = data.get('Keywords') or [job.get('Name') or 'Busca no mapa']
        if not isinstance(keywords, list):
            keywords = [str(keywords)]
        b = previous or {'id': 'sith_' + jid.replace('-', ''), 'criado_em': now,
                         'parametros': {'nichos': [str(k).split(' em ')[0][:200] for k in keywords[:10]],
                                        'cidade': next((e['cidade'] for e in empresas if e['cidade']), ''),
                                        'uf': next((e['uf'] for e in empresas if e['uf']), ''),
                                        'bairro': '', 'tamanho': 'scraper', 'redes': False},
                         'jobs_motor': [], 'avisos': [], 'lead_ids': []}
        novos = sum(e['id'] not in leads for e in empresas)
        atualizados = sum(e['id'] in leads and any(e.get(k) not in (None, '') and e.get(k) != leads[e['id']].get(k)
                                                  for k in CAMPOS_CONTATO) for e in empresas)
        ids = mesclar_leads(b, empresas)
        b['lead_ids'] = list(dict.fromkeys(b.get('lead_ids', []) + ids))
        b.update(estado='concluida', etapa='Importada do SITH.IA Scraper', origem='sithia_scraper',
                 scraper_job_id=jid, importado_em=now, concluido_em=b.get('concluido_em') or now,
                 novos=novos, parcial=0, progresso=None)
        buscas[b['id']] = b
        salvar_leads()
        salvar_busca(b)
        return {'busca_id': b['id'], 'total': len(ids), 'novos': novos, 'atualizados': atualizados}
