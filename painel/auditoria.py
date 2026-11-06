"""Coleta auditável de sinais públicos de uma empresa."""
import json
import os
import re
import time
from urllib.parse import urlencode, urlsplit, urlunsplit
from auditoria_cnpj import consultar
from auditoria_http import FalhaHTTP, obter
from auditoria_site import Pagina, contatos, host, normal, perfil_instagram, tecnologias, whatsapp


def _url_site(valor):
    if not isinstance(valor, str) or not valor.strip():
        return ''
    valor = valor.strip()
    try:
        u = urlsplit(valor if '://' in valor else 'https://' + valor)
        return urlunsplit((u.scheme, u.netloc, u.path, '', ''))
    except ValueError:
        return ''


def bibliotecas(lead):
    nome = str(lead.get('nome') or '')[:180]
    dominio = host(_url_site(lead.get('site')))
    google = {'region': 'BR'}
    if dominio and dominio not in {'instagram.com', 'facebook.com', 'wa.me', 'linktr.ee'}:
        google['domain'] = dominio
    meta = {'active_status': 'active', 'ad_type': 'all', 'country': 'BR', 'q': nome,
            'search_type': 'keyword_unordered'}
    return {'google': 'https://adstransparency.google.com/?' + urlencode(google),
            'meta': 'https://www.facebook.com/ads/library/?' + urlencode(meta)}


def _pagina(resposta):
    if 200 <= resposta['status'] < 300 and resposta['tipo'] in ('text/html', 'application/xhtml+xml'):
        return Pagina(resposta['texto'], resposta['url'])
    return None


def _site(url):
    url = _url_site(url)
    if not url:
        return {'estado': 'sem_site'}, []
    if host(url) in {'instagram.com', 'facebook.com', 'wa.me', 'linktr.ee'}:
        return {'estado': 'somente_perfil', 'url': url}, []
    try:
        resposta = obter(url)
    except FalhaHTTP as e:
        return {'estado': 'indisponivel', 'motivo': str(e)}, []
    dados = {k: resposta[k] for k in ('url', 'status', 'ttfb_ms', 'ms', 'bytes', 'truncado')}
    dados['estado'] = 'respondendo' if 200 <= resposta['status'] < 300 else 'erro_http'
    inicial = _pagina(resposta)
    if not inicial:
        return dados, []
    dados.update(titulo=inicial.titulo, descricao=inicial.metadados.get('description', ''),
                 responsivo=bool(inicial.metadados.get('viewport')), h1=inicial.h1,
                 imagens=inicial.img, imagens_sem_alt=inicial.sem_alt,
                 noindex='noindex' in inicial.metadados.get('robots', '').lower(),
                 https=inicial.url.startswith('https://'))
    paginas = [inicial]
    vistas = {inicial.url}
    for link in inicial.links:
        if len(vistas) >= 4:
            break
        if host(link) != host(inicial.url) or not link.startswith(('http://', 'https://')):
            continue
        u = urlsplit(link)
        if not re.search(r'contat|sobre|quem.somos|equipe|privacidade|institucional', normal(u.path)):
            continue
        limpo = urlunsplit((u.scheme, u.netloc, u.path, '', ''))
        if limpo in vistas:
            continue
        vistas.add(limpo)
        try:
            extra = _pagina(obter(limpo, timeout=5))
        except FalhaHTTP:
            continue
        if extra and host(extra.url) == host(inicial.url):
            paginas.append(extra)
    dados['paginas'] = [p.url for p in paginas]
    return dados, paginas


def _velocidade(url):
    link = 'https://pagespeed.web.dev/analysis?' + urlencode({'url': url})
    chave = os.environ.get('SITH_PAGESPEED_KEY')
    if not chave:
        return {'estado': 'sem_chave', 'url': link}
    endpoint = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?' + urlencode(
        {'url': url, 'strategy': 'mobile', 'category': 'performance', 'key': chave})
    try:
        r = obter(endpoint, hosts={'www.googleapis.com'}, timeout=30, limite=5_000_000)
        if r['status'] == 200:
            dados = json.loads(r['texto']).get('lighthouseResult') or {}
            nota = dados.get('categories', {}).get('performance', {}).get('score')
            if isinstance(nota, (int, float)) and 0 <= nota <= 1:
                metricas = {}
                for chave_metrica, rotulo in (('largest-contentful-paint', 'LCP'),
                                             ('total-blocking-time', 'TBT'), ('cumulative-layout-shift', 'CLS')):
                    valor = dados.get('audits', {}).get(chave_metrica, {}).get('displayValue')
                    if isinstance(valor, str):
                        metricas[rotulo] = valor[:50]
                return {'estado': 'medido', 'url': link, 'nota': round(nota * 100), 'metricas': metricas}
    except (FalhaHTTP, ValueError, AttributeError, TypeError):
        pass
    return {'estado': 'indisponivel', 'url': link}


def _testar_whatsapp(paginas):
    link = whatsapp(paginas)
    if not link:
        return {'estado': 'nao_detectado'}
    if not link['url']:
        return {**link, 'estado': 'sem_numero'}
    try:
        r = obter(link['url'], hosts={'wa.me', 'api.whatsapp.com', 'web.whatsapp.com',
                                    'www.whatsapp.com', 'whatsapp.com'}, timeout=6, limite=100_000)
        if r['status'] in (404, 410):
            return {**link, 'estado': 'erro_http', 'status': r['status']}
        if 200 <= r['status'] < 300:
            texto = normal(r['texto'])
            invalido = any(s in texto for s in ('phone number shared via url is invalid',
                                               'phone number is not on whatsapp', 'numero de telefone invalido'))
            return {**link, 'estado': 'numero_invalido' if invalido else 'link_responde'}
    except FalhaHTTP:
        pass
    return {**link, 'estado': 'inconclusivo'}


def _instagram(lead, paginas):
    candidatos = [lead.get('instagram'), _url_site(lead.get('site'))] + [link for p in paginas for link in p.links]
    url = next((p for c in candidatos if (p := perfil_instagram(c))), '')
    if not url:
        return {'estado': 'nao_identificado'}
    try:
        r = obter(url, hosts={'www.instagram.com', 'instagram.com'}, timeout=6, limite=250_000)
        pagina = _pagina(r)
        if pagina and perfil_instagram(r['url']) == url:
            titulo = pagina.metadados.get('og:title', '')
            descricao = pagina.metadados.get('og:description', '')
            conta = urlsplit(url).path.strip('/')
            if titulo and descricao and '@' + conta.lower() in (titulo + ' ' + descricao).lower():
                return {'estado': 'perfil_publico', 'url': url, 'titulo': titulo[:200], 'descricao': descricao[:450]}
    except FalhaHTTP:
        pass
    return {'estado': 'leitura_limitada', 'url': url}


def auditar(lead, cnpj=''):
    site, paginas = _site(lead.get('site'))
    velocidade = _velocidade(_url_site(site['url'])) if site.get('estado') == 'respondendo' and paginas else {'estado': 'sem_medicao'}
    return {'atualizado_em': time.time(), 'site': site, 'velocidade': velocidade,
            'cadastro': consultar(lead, paginas, cnpj), 'contatos': contatos(paginas),
            'whatsapp': _testar_whatsapp(paginas), 'instagram': _instagram(lead, paginas),
            'tags': tecnologias(paginas)}
