"""Rotas protegidas, fila local e persistência da auditoria na ficha do lead."""
import json
import queue
import re
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

from auditoria import auditar, bibliotecas
from auditoria_site import cnpj_valido
from campanhas import SEGMENTOS
from estado import buscas, leads, lock, salvar_leads
from oportunidades import GRUPOS, PRIORIDADES, oportunidade, prospectavel

LIMITE_FILA = 200
fila = queue.Queue()
pendentes = {}
falhas = set()
trabalhador = None


class ErroAuditoria(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status


def _lead(lid):
    lead = leads.get(lid)
    if lead is None:
        raise ErroAuditoria(404, 'Lead não encontrado.')
    return lead


def _salvar(lead, dados):
    anterior = lead.get('auditoria')
    lead['auditoria'] = dados
    try:
        salvar_leads()
    except OSError:
        if anterior is None:
            lead.pop('auditoria', None)
        else:
            lead['auditoria'] = anterior
        raise


def _trabalhar():
    while True:
        lid, original, cnpj = fila.get()
        try:
            with lock:
                if leads.get(lid) is not original:
                    continue
                pendentes[lid] = 'executando'
                empresa = {k: original.get(k) for k in ('site', 'nome', 'cidade', 'uf', 'instagram')}
            relatorio = auditar(empresa, cnpj)
            with lock:
                if leads.get(lid) is original:
                    dados = dict(original.get('auditoria') or {}, relatorio=relatorio, cnpj_informado=cnpj)
                    _salvar(original, dados)
        except Exception:
            with lock:
                if leads.get(lid) is original:
                    falhas.add(lid)
        finally:
            with lock:
                pendentes.pop(lid, None)
            fila.task_done()


def _enfileirar(ids, cnpj=None, somente_novas=False):
    global trabalhador
    resultado = {'na_fila': 0, 'ja_em_andamento': 0, 'ja_auditadas': 0, 'sem_vaga': 0}
    for lid in dict.fromkeys(ids):
        lead = leads.get(lid)
        if lead is None:
            continue
        auditoria = lead.get('auditoria') or {}
        if lid in pendentes:
            resultado['ja_em_andamento'] += 1
        elif somente_novas and auditoria.get('relatorio'):
            resultado['ja_auditadas'] += 1
        elif len(pendentes) >= LIMITE_FILA:
            resultado['sem_vaga'] += 1
        else:
            pendentes[lid] = 'na_fila'
            falhas.discard(lid)
            informado = auditoria.get('cnpj_informado', '') if cnpj is None else cnpj
            fila.put_nowait((lid, lead, informado))
            resultado['na_fila'] += 1
    if resultado['na_fila'] and (trabalhador is None or not trabalhador.is_alive()):
        trabalhador = threading.Thread(target=_trabalhar, daemon=True, name='auditoria-digital')
        trabalhador.start()
    return resultado


def programar_automaticas():
    with lock:
        if len(pendentes) >= LIMITE_FILA:
            return
        ids = [lid for lid, lead in leads.items() if prospectavel(lead) and lid not in falhas]
        return _enfileirar(ids, somente_novas=True)


def agendar_automaticas():
    while True:
        programar_automaticas()
        time.sleep(8)


def _estado(lid, audit):
    if lid in pendentes:
        return pendentes[lid]
    if lid in falhas:
        return 'falhou'
    return 'concluida' if audit.get('relatorio') else 'nao_executada'


def _resumo(lid, lead):
    audit = lead.get('auditoria') or {}
    return {'estado': _estado(lid, audit), 'relatorio': audit.get('relatorio'),
            'cnpj_informado': audit.get('cnpj_informado', ''),
            'anuncios': audit.get('anuncios', {}), 'bibliotecas': bibliotecas(lead)}


def _anuncio(lead, d):
    plataforma, estado = d.get('plataforma'), d.get('estado')
    url = d.get('url') or ''
    if (plataforma not in ('meta', 'google') or estado not in ('pendente', 'encontrado', 'nao_localizado')
            or not isinstance(url, str) or len(url) > 1600 or re.search(r'[\x00-\x20\x7f]', url)):
        raise ErroAuditoria(400, 'Verificação de anúncio inválida.')
    if estado == 'encontrado' and not url:
        raise ErroAuditoria(400, 'Informe o link oficial onde encontrou o anúncio.')
    if url:
        try:
            u = urlsplit(url)
            meta = u.hostname in {'facebook.com', 'www.facebook.com', 'business.facebook.com'} and u.path.rstrip('/') == '/ads/library'
            google = u.hostname == 'adstransparency.google.com' and (u.path == '/' or u.path.startswith('/advertiser/'))
            permitido = meta if plataforma == 'meta' else google
            if u.scheme != 'https' or not permitido or u.username is not None or u.port not in (None, 443):
                raise ValueError
            if set(parse_qs(u.query, keep_blank_values=True)) & {'access_token', 'token', 'key'}:
                raise ValueError
        except ValueError as e:
            raise ErroAuditoria(400, 'Use um link da biblioteca oficial selecionada.') from e
    dados = dict(lead.get('auditoria') or {})
    anuncios = dict(dados.get('anuncios') or {})
    if estado == 'pendente':
        anuncios.pop(plataforma, None)
    else:
        anuncios[plataforma] = {'estado': estado, 'url': url or bibliotecas(lead)[plataforma],
                                'verificado_em': time.time()}
    _salvar(lead, dict(dados, anuncios=anuncios))


def atender(h, metodo, path):
    if metodo == 'GET' and path == '/api/oportunidades':
        _listar_oportunidades(h)
        return True
    mini = re.fullmatch(r'/api/leads/([^/]+)/oportunidade', path)
    if metodo == 'GET' and mini:
        with lock:
            lead = leads.get(unquote(mini[1]))
            item = _mini(lead) if lead and prospectavel(lead) else None
        h._envia(200, {'item': item, 'grupos': GRUPOS, 'prioridades': PRIORIDADES})
        return True
    lead_match = re.fullmatch(r'/api/leads/([^/]+)/auditoria(/anuncios)?', path)
    busca_match = re.fullmatch(r'/api/buscas/([\w-]+)/auditoria', path)
    if not lead_match and not busca_match:
        return False
    try:
        somente_post = busca_match or (lead_match and lead_match[2])
        if metodo not in ('GET', 'POST') or somente_post and metodo != 'POST':
            raise ErroAuditoria(405, 'Método não permitido.')
        d = h._corpo() if metodo == 'POST' else {}
        if not isinstance(d, dict):
            raise ErroAuditoria(400, 'Envie os parâmetros da auditoria.')
        with lock:
            if busca_match:
                busca = buscas.get(busca_match[1])
                if busca is None or busca.get('lixeira_em'):
                    raise ErroAuditoria(404, 'Busca não encontrada.')
                resposta, status = _enfileirar(busca.get('lead_ids', []), somente_novas=True), 202
            else:
                lid = unquote(lead_match[1])
                lead = _lead(lid)
                status = 200
                if lead_match[2]:
                    _anuncio(lead, d)
                elif metodo == 'POST':
                    valor = d.get('cnpj', '')
                    cnpj = cnpj_valido(valor)
                    if not isinstance(valor, str) or valor and not cnpj:
                        raise ErroAuditoria(400, 'Informe um CNPJ válido.')
                    if _enfileirar([lid], cnpj)['sem_vaga']:
                        raise ErroAuditoria(429, 'A fila de auditorias está cheia. Tente mais tarde.')
                    status = 202
                resposta = _resumo(lid, lead)
        h._envia(status, resposta)
    except ErroAuditoria as e:
        h._envia(e.status, {'erro': str(e)})
    except (json.JSONDecodeError, UnicodeError):
        h._envia(400, {'erro': 'JSON inválido.'})
    except OSError:
        h._envia(503, {'erro': 'Não foi possível salvar a auditoria.'})
    return True


def _mini(lead):
    return oportunidade(lead, _estado(lead['id'], lead.get('auditoria') or {}))


def _listar_oportunidades(h):
    params = parse_qs(urlsplit(h.path).query)
    grupo = params.get('grupo', [''])[0]
    segmento = params.get('segmento', [''])[0]
    prioridade = params.get('prioridade', [''])[0]
    try:
        pagina = max(1, int(params.get('pagina', ['1'])[0]))
    except ValueError:
        pagina = 1
    with lock:
        itens = [_mini(lead) for lead in leads.values() if prospectavel(lead)]
    if segmento:
        itens = [x for x in itens if x['segmento'] == segmento]
    resumo = {k: sum(x['prioridade'] == k for x in itens) for k in PRIORIDADES}
    auditorias = {k: sum(x['auditoria'] == k for x in itens)
                  for k in ('nao_executada', 'na_fila', 'executando', 'concluida', 'falhou')}
    grupos = {k: {**d, 'total': sum(x['grupo'] == k for x in itens)} for k, d in GRUPOS.items()}
    if grupo:
        itens = [x for x in itens if x['grupo'] == grupo]
    if prioridade:
        itens = [x for x in itens if x['prioridade'] == prioridade]
    ordem = {k: n for n, k in enumerate(PRIORIDADES)}
    itens.sort(key=lambda x: (ordem[x['prioridade']], x['nome'].casefold()))
    tamanho = 24
    paginas = max(1, (len(itens) + tamanho - 1) // tamanho)
    pagina = min(pagina, paginas)
    inicio = (pagina - 1) * tamanho
    h._envia(200, {'grupos': grupos, 'prioridades': PRIORIDADES, 'total': len(itens),
                   'pagina': pagina, 'paginas': paginas, 'itens': itens[inicio:inicio + tamanho],
                   'campanha': SEGMENTOS.get(segmento, {}).get('nome', ''),
                   'resumo': resumo, 'auditorias': auditorias})
