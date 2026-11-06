"""HTTP público para auditorias. Conecta ao IP validado e mantém Host e TLS do domínio."""
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit


class FalhaHTTP(Exception):
    pass


def destino(url, hosts=None):
    if re.search(r'[\x00-\x1f\x7f]', url):
        raise FalhaHTTP('Endereço inválido.')
    try:
        u = urlsplit(url)
        porta = {'http': 80, 'https': 443}.get(u.scheme)
        if (not porta or not u.hostname or u.username is not None or u.password is not None
                or u.port not in (None, porta) or '\\' in u.netloc):
            raise FalhaHTTP('Endereço HTTP público inválido.')
        host = u.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        if hosts is not None and host not in hosts:
            raise FalhaHTTP('Redirecionamento fora da fonte consultada.')
        enderecos = socket.getaddrinfo(host, porta, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(ipaddress.ip_address(r[4][0]) for r in enderecos))
    except (OSError, UnicodeError, ValueError) as e:
        raise FalhaHTTP('Domínio indisponível ou inválido.') from e
    if not ips or any(not ip.is_global or ip.is_multicast or ip.is_reserved for ip in ips):
        raise FalhaHTTP('A auditoria só visita endereços públicos.')
    caminho = quote(u.path or '/', safe="/%:@!$&'()*+,;=-._~")
    if u.query:
        caminho += '?' + quote(u.query, safe="/%:@!$&'()*+,;=?-._~")
    return u.scheme, host, porta, str(ips[0]), caminho


def obter(url, *, hosts=None, timeout=7, limite=768_000, somente_status=False):
    inicio = time.monotonic()

    def restante():
        tempo = timeout - (time.monotonic() - inicio)
        if tempo <= 0:
            raise FalhaHTTP('Tempo limite de consulta.')
        return tempo

    for _ in range(5):
        scheme, host, porta, ip, caminho = destino(url, hosts)
        classe = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
        conn = classe(host, porta, timeout=restante())
        conn._create_connection = lambda _, tempo, origem: socket.create_connection((ip, porta), tempo, origem)
        resp = None
        try:
            conn.connect()
            sock = conn.sock
            sock.settimeout(restante())
            conn.request('GET', caminho, headers={'User-Agent': 'Mozilla/5.0 (compatible; SITHIA-Auditoria/1.0)',
                                                  'Accept-Encoding': 'identity'})
            sock.settimeout(restante())
            resp = conn.getresponse()
            ttfb = round((time.monotonic() - inicio) * 1000)
            redirecionamento = resp.getheader('Location')
            if resp.status in (301, 302, 303, 307, 308) and redirecionamento:
                url = urljoin(url, redirecionamento)
                continue
            tipo = resp.headers.get_content_type()
            bruto = bytearray()
            if not somente_status and tipo in ('text/html', 'application/xhtml+xml', 'application/json', 'text/plain'):
                while len(bruto) <= limite:
                    sock.settimeout(restante())
                    parte = resp.read1(min(32768, limite + 1 - len(bruto)))
                    if not parte:
                        break
                    bruto.extend(parte)
            charset = resp.headers.get_content_charset() or 'utf-8'
            try:
                texto = bruto[:limite].decode(charset, errors='replace')
            except LookupError:
                texto = bruto[:limite].decode('utf-8', errors='replace')
            return {'url': url, 'status': resp.status, 'tipo': tipo, 'texto': texto,
                    'ttfb_ms': ttfb, 'ms': round((time.monotonic() - inicio) * 1000),
                    'bytes': min(len(bruto), limite), 'truncado': len(bruto) > limite}
        except ssl.SSLCertVerificationError as e:
            raise FalhaHTTP('O certificado HTTPS não pôde ser validado nesta conexão.') from e
        except (OSError, http.client.HTTPException, UnicodeError) as e:
            raise FalhaHTTP('O servidor não respondeu à consulta HTTP.') from e
        finally:
            if resp is not None:
                resp.close()
            conn.close()
    raise FalhaHTTP('Muitos redirecionamentos.')
