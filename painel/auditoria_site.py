"""Evidência estática publicada no site da empresa."""
import json
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlsplit


def normal(texto):
    txt = unicodedata.normalize('NFKD', str(texto or '').lower())
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in txt if not unicodedata.combining(c))))


def host(url):
    try:
        return (urlsplit(url).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''


def cnpj_valido(valor):
    if not isinstance(valor, str):
        return ''
    numero = re.sub(r'[.\s/-]', '', valor.upper())
    if not re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', numero) or len(set(numero)) == 1:
        return ''
    base = numero[:12]
    for pesos in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        resto = sum((ord(c) - 48) * p for c, p in zip(base, pesos)) % 11
        base += str(11 - resto if resto >= 2 else 0)
    return numero if numero == base else ''


class Pagina(HTMLParser):
    def __init__(self, html, url):
        super().__init__(convert_charrefs=True)
        self.url, self.links, self.scripts, self.metadados = url, [], [], {}
        self.texto, self.pessoas, self.documentos = [], [], []
        self.contatos_nomeados, self._ancora = [], None
        self.titulo, self.h1, self.img, self.sem_alt = '', 0, 0, 0
        self._script, self._titulo, self._estilo = None, False, False
        self.feed(html)

    def _link(self, valor):
        try:
            return urljoin(self.url, valor)
        except ValueError:
            return ''

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script':
            self._script = a.get('type') or 'js'
            if a.get('src'):
                self.scripts.append(self._link(a['src']))
        elif tag == 'a' and a.get('href') and len(self.links) < 1500:
            href = self._link(a['href'])
            self.links.append(href)
            if href.lower().startswith(('mailto:', 'tel:')):
                self._ancora = (href, [a.get('aria-label') or '', a.get('title') or ''])
        elif tag == 'meta':
            chave = a.get('name') or a.get('property')
            if chave and a.get('content'):
                self.metadados[chave.lower()] = a['content'][:700]
        elif tag == 'title':
            self._titulo = True
        elif tag == 'style':
            self._estilo = True
        elif tag == 'h1':
            self.h1 += 1
        elif tag == 'img':
            self.img += 1
            self.sem_alt += int('alt' not in a)

    def handle_endtag(self, tag):
        if tag == 'script':
            self._script = None
        elif tag == 'title':
            self._titulo = False
        elif tag == 'style':
            self._estilo = False
        elif tag == 'a' and self._ancora:
            href, rotulos = self._ancora
            self.contatos_nomeados.append((href, rotulos))
            self._ancora = None

    def handle_data(self, data):
        if self._script == 'application/ld+json':
            try:
                self._estruturado(json.loads(data))
            except (ValueError, RecursionError):
                pass
        elif self._script:
            self.scripts.append(data)
        elif not self._estilo:
            self.texto.append(data)
            if self._ancora:
                self._ancora[1].append(data)
            if self._titulo:
                self.titulo = (self.titulo + data)[:250]

    def _estruturado(self, item, nivel=0):
        if nivel > 10:
            return
        if isinstance(item, dict):
            tipo = item.get('@type', [])
            if tipo == 'Person' or isinstance(tipo, list) and 'Person' in tipo:
                self.pessoas.append(item)
            for campo in ('taxID', 'vatID'):
                if cnpj := cnpj_valido(item.get(campo)):
                    self.documentos.append(cnpj)
            for v in item.values():
                self._estruturado(v, nivel + 1)
        elif isinstance(item, list):
            for v in item:
                self._estruturado(v, nivel + 1)

    def cnpjs(self):
        texto = ' '.join(self.texto)
        fmt = r'(?<![\w])([A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-[0-9]{2})(?!\w)'
        rotulo = r'\bCNPJ\s*[:#–-]?\s*([A-Z0-9]{12}[0-9]{2})(?!\w)'
        encontrados = re.findall(fmt, texto, re.I) + re.findall(rotulo, texto, re.I)
        return list(dict.fromkeys(self.documentos + [n for x in encontrados if (n := cnpj_valido(x))]))


def contatos(paginas):
    emails, telefones = {}, {}
    for pagina in paginas:
        for link in pagina.links:
            if link.lower().startswith('mailto:'):
                email = unquote(link[7:].split('?', 1)[0]).strip().lower()
                if re.fullmatch(r'[^\s@,]+@[^\s@,]+\.[a-z]{2,}', email) and len(email) <= 160:
                    emails.setdefault(email, pagina.url)
            elif link.lower().startswith('tel:'):
                telefone = re.sub(r'\D', '', link[4:])
                if 8 <= len(telefone) <= 15:
                    telefones.setdefault(telefone, pagina.url)
    return {'emails': [{'valor': v, 'fonte': f} for v, f in list(emails.items())[:15]],
            'telefones': [{'valor': v, 'fonte': f} for v, f in list(telefones.items())[:15]]}


def tecnologias(paginas):
    sinais = {}
    regras = {
        'Meta Pixel': r'connect\.facebook\.net/[^\s"]*/fbevents\.js|\bfbq\s*\(\s*[\'"]init[\'"]',
        'Google Ads': r'\bAW-[0-9]{5,}\b|googleadservices\.com/pagead/conversion',
        'Google Analytics': r'\bG-[A-Z0-9]{6,}\b|google-analytics\.com/(?:analytics|ga)\.js',
        'Google Tag Manager': r'\bGTM-[A-Z0-9]{4,}\b|googletagmanager\.com/gtm\.js',
    }
    for pagina in paginas:
        codigo = '\n'.join(pagina.scripts)
        for nome, regex in regras.items():
            if nome not in sinais and (m := re.search(regex, codigo, re.I)):
                sinais[nome] = {'nome': nome, 'fonte': pagina.url, 'evidencia': m.group()[:130]}
    return list(sinais.values())


def perfil_instagram(url):
    if not isinstance(url, str) or host(url) != 'instagram.com':
        return ''
    try:
        conta = urlsplit(url).path.strip('/')
    except ValueError:
        return ''
    if (re.fullmatch(r'[A-Za-z0-9._]{1,30}', conta) and
            conta.lower() not in {'p', 'reel', 'reels', 'stories', 'accounts', 'explore', 'direct', 'about', 'share'}):
        return 'https://www.instagram.com/' + conta + '/'
    return ''


def whatsapp(paginas):
    sem_numero = None
    for pagina in paginas:
        for link in pagina.links:
            dominio = host(link)
            if dominio not in {'wa.me', 'api.whatsapp.com', 'web.whatsapp.com', 'whatsapp.com'}:
                continue
            try:
                u = urlsplit(link)
            except ValueError:
                continue
            if dominio != 'wa.me' and u.path.rstrip('/') != '/send':
                continue
            numero = u.path.strip('/') if dominio == 'wa.me' else parse_qs(u.query).get('phone', [''])[0]
            if re.fullmatch(r'[1-9][0-9]{7,14}', numero):
                return {'url': 'https://wa.me/' + numero, 'fonte': pagina.url}
            sem_numero = {'url': '', 'fonte': pagina.url}
    return sem_numero
