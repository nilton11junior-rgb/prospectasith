"""Exclusão completa, confirmada por resumo: busca, leads e referências locais."""
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import uuid
from copy import deepcopy
from estado import (ARQ_AGENDA, ARQ_CONFIG, ARQ_CONVERSAS, ARQ_LEADS, DADOS, DIR_BUSCAS,
                    _grava, _le, agenda_dados, buscas, config, conversas, fila, kit, leads, lock, pendentes_ia)

ARQ_EXCLUSOES = os.path.join(DADOS, 'exclusoes_buscas.json')


class ErroExclusao(Exception):
    def __init__(self, status, texto):
        super().__init__(texto)
        self.status = status


def _snapshot():
    return json.loads(json.dumps(dict(buscas=buscas, leads=leads, conversas=conversas,
                                    agenda=agenda_dados, config=config,
                                    exclusoes=_le(ARQ_EXCLUSOES, {}))))


def _plano(ids):
    if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or any(
            not isinstance(i, str) or not re.fullmatch(r'[\w-]{1,100}', i, re.ASCII) for i in ids):
        raise ErroExclusao(400, 'Selecione uma ou mais buscas válidas.')
    ids = sorted(set(ids))
    if any(i not in buscas for i in ids):
        raise ErroExclusao(404, 'Uma busca não existe mais. Atualize a lista.')
    if any(buscas[i].get('estado') in ('rodando', 'na_fila') for i in ids):
        raise ErroExclusao(409, 'Cancele as buscas em andamento antes de excluir.')
    alvos = {lid for i in ids for lid in buscas[i].get('lead_ids', [])}
    alvos.update(lid for i in ids for lid in buscas[i].get('lixeira_leads', {}))
    alvos.update(lid for lid, lead in leads.items() if set(lead.get('buscas', [])) & set(ids))
    todos = {**{lid: l for b in buscas.values() for lid, l in b.get('lixeira_leads', {}).items()}, **leads}
    existentes = alvos & todos.keys()
    if any(bid not in ids and b.get('estado') in ('rodando', 'na_fila') and set(b.get('lead_ids', [])) & alvos
           for bid, b in buscas.items()):
        raise ErroExclusao(409, 'Cancele a outra busca em andamento que compartilha esses leads.')
    cv = [n for n, c in conversas.items() if c.get('lead_id') in alvos]
    reservas = [r for r in agenda_dados.get('reservas', []) if r.get('lead_id') in alvos]
    resumo = dict(ids=ids, buscas=len(ids), leads=len(existentes), conversas=len(cv), reservas=len(reservas),
                  compartilhados=sum(bool(set(todos[lid].get('buscas', [])) - set(ids)) for lid in existentes),
                  trabalhados=sum(todos[lid].get('status', 'novo') != 'novo' or bool(todos[lid].get('obs'))
                                  or len(todos[lid].get('historico', [])) > 1 for lid in existentes))
    escopo = {'ids': ids, 'buscas': [buscas[i] for i in ids], 'leads': {i: todos.get(i) for i in sorted(alvos)},
              'conversas': {n: conversas[n] for n in cv}, 'reservas': reservas,
              'referencias': {i: sorted(set(b.get('lead_ids', [])) & alvos) for i, b in buscas.items()
                              if set(b.get('lead_ids', [])) & alvos},
              'guardados': {i: {lid: l for lid, l in b.get('lixeira_leads', {}).items() if lid in alvos}
                            for i, b in buscas.items() if set(b.get('lixeira_leads', {})) & alvos},
              'auto': config.get('auto_envio', {})}
    assinatura = json.dumps(escopo, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    resumo['confirmacao'] = hashlib.sha256(assinatura).hexdigest()
    return resumo, alvos


def previa(ids):
    with lock:
        return _plano(ids)[0]


def backup(snapshot):
    pasta = os.path.join(DADOS, 'backups', 'exclusoes', time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    os.makedirs(pasta, exist_ok=False)
    _grava(os.path.join(pasta, 'snapshot.json'), snapshot)
    return os.path.basename(pasta)


def _gravar(snapshot, anteriores):
    for arquivo, chave in ((ARQ_LEADS, 'leads'), (ARQ_CONVERSAS, 'conversas'),
                           (ARQ_AGENDA, 'agenda'), (ARQ_CONFIG, 'config'), (ARQ_EXCLUSOES, 'exclusoes')):
        _grava(arquivo, snapshot[chave])
    for bid, b in snapshot['buscas'].items():
        _grava(os.path.join(DIR_BUSCAS, bid + '.json'), b)
    for bid in set(anteriores) - snapshot['buscas'].keys():
        try:
            os.remove(os.path.join(DIR_BUSCAS, bid + '.json'))
        except FileNotFoundError:
            pass


def _remover_leads(snapshot, alvos):
    for lid in alvos:
        snapshot['leads'].pop(lid, None)
    for b in snapshot['buscas'].values():
        ids = b.get('lead_ids', [])
        if alvos.intersection(ids):
            b['lead_ids'] = [lid for lid in ids if lid not in alvos]
            if b.get('novos') is not None:
                b['novos'] = min(b['novos'], len(b['lead_ids']))
        if 'lixeira_leads' in b:
            b['lixeira_leads'] = {lid: l for lid, l in b['lixeira_leads'].items() if lid not in alvos}
    snapshot['conversas'] = {n: c for n, c in snapshot['conversas'].items() if c.get('lead_id') not in alvos}
    snapshot['agenda']['reservas'] = [
        r for r in snapshot['agenda'].get('reservas', []) if r.get('lead_id') not in alvos
    ]


def _persistir(antes, depois, alvos):
    copia = backup(antes)
    try:
        _gravar(depois, antes['buscas'])
    except OSError:
        _gravar(antes, depois['buscas'])
        raise
    removidas = antes['buscas'].keys() - depois['buscas'].keys()
    for bid in removidas:
        buscas[bid]['_excluida'] = True
        buscas.pop(bid)
    # Mantenha as referências usadas pelos trabalhadores das buscas restantes.
    for bid, b in buscas.items():
        novo = depois['buscas'][bid]
        for campo in ('lead_ids', 'novos', 'lixeira_leads'):
            if campo in novo and novo[campo] != b.get(campo):
                b[campo] = novo[campo]
    for lid in alvos:
        removido = leads.pop(lid, None)
        if removido is not None:
            removido['_excluido'] = True
    cvs = antes['conversas'].keys() - depois['conversas'].keys()
    for n in cvs:
        conversas.pop(n, None)
    reservas = agenda_dados.setdefault('reservas', [])
    reservas[:] = [r for r in reservas if r.get('lead_id') not in alvos]
    auto = depois['config'].get('auto_envio', {})
    if auto != antes['config'].get('auto_envio', {}):
        config.setdefault('auto_envio', {}).update(auto)
    fila[:] = [bid for bid in fila if bid not in removidas]
    numeros = {re.sub(r'\D', '', str(antes['leads'].get(lid, {}).get(campo) or ''))
               for lid in alvos for campo in ('whatsapp', 'tel_digitos')} - {''}
    for n in list(pendentes_ia):
        if n in cvs or (n not in conversas and re.sub(r'\D', '', n) in numeros):
            pendentes_ia.pop(n, None)
    return copia


def excluir_lead(lid):
    with lock:
        if lid not in leads:
            raise ErroExclusao(404, 'Lead não encontrado.')
        antes = _snapshot()
        depois = deepcopy(antes)
        _remover_leads(depois, {lid})
        return {'id': lid, 'backup': _persistir(antes, depois, {lid})}


def excluir(ids, confirmacao):
    with lock:
        resumo, alvos = _plano(ids)
        if not isinstance(confirmacao, str) or not hmac.compare_digest(confirmacao, resumo['confirmacao']):
            raise ErroExclusao(409, 'A lista mudou ou falta confirmação. Confira o resumo novamente.')
        antes = _snapshot()
        depois = deepcopy(antes)
        removidas = [depois['buscas'].pop(i) for i in resumo['ids']]
        _remover_leads(depois, alvos)
        auto = depois['config'].get('auto_envio', {})
        filtros = auto.get('buscas', [])
        auto['buscas'] = [bid for bid in filtros if bid not in resumo['ids']]
        if filtros and not auto['buscas']:
            auto['ativo'] = False
        excl = depois['exclusoes']
        for b in removidas:
            for motor, jid in [('original', j) for j in b.get('jobs_motor', [])] + [('scraper', b.get('scraper_job_id'))]:
                if jid:
                    excl[motor + ':' + str(jid)] = {'motor': motor, 'id': str(jid), 'pendente': True}
        copia = _persistir(antes, depois, alvos)
        return {**resumo, 'backup': copia, 'limpeza_pendente': sum(j.get('pendente', False) for j in excl.values())}


def job_excluido(jid):
    return 'scraper:' + str(jid) in _le(ARQ_EXCLUSOES, {})


def limpar_pendentes():
    """Motor offline não impede limpar o CRM; os IDs excluídos continuam bloqueados."""
    with lock:
        pendentes = list(_le(ARQ_EXCLUSOES, {}).items())
    for chave, job in pendentes:
        if not job.get('pendente'):
            continue
        try:
            jid = str(uuid.UUID(job['id']))
            if job['motor'] == 'scraper':
                from scraper_motor import request, ScraperError
                try:
                    request('DELETE', '/api/v1/jobs/' + jid)
                except ScraperError as erro:
                    if erro.status != 404:
                        continue
            else:
                try:
                    kit.req('DELETE', '/api/v1/jobs/' + jid)
                except urllib.error.HTTPError as erro:
                    if erro.code != 404:
                        continue
        except Exception:
            continue
        with lock:
            atual = _le(ARQ_EXCLUSOES, {})
            if chave in atual:
                atual[chave]['pendente'] = False
                _grava(ARQ_EXCLUSOES, atual)


def trabalhador_limpeza():
    while True:
        try:
            limpar_pendentes()
        except OSError:
            pass
        time.sleep(30)
