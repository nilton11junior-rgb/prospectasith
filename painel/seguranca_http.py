"""Barreiras HTTP do painel: hosts e origens permitidos (DNS rebinding e CSRF), limite de corpo,
bloqueio de força bruta no login e cabeçalhos de segurança."""
import time, urllib.parse
from estado import lock


LIMITE_CORPO = 1_000_000
HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")
CABECALHOS_SEGURANCA = (
    ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' "
     "https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; "
     "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
)
_falhas_login = []  # horários das senhas erradas recentes (global: o servidor atende em paralelo)


def nome_host(valor):
    """'localhost:8090' -> 'localhost'; '[::1]:8090' -> '::1'; inválido -> ''."""
    try:
        return (urllib.parse.urlsplit("//" + (valor or "")).hostname or "").lower()
    except ValueError:
        return ""


def host_permitido(host, webhook=False):
    return host in HOSTS_LOCAIS or host.endswith(".ts.net") or (webhook and host == "host.docker.internal")


def origem_permitida(origem, host):
    """Origin do navegador precisa ser o próprio painel (mesmo nome e porta do Host pedido)."""
    try:
        o = urllib.parse.urlsplit(origem)
    except ValueError:
        return False
    return o.scheme in ("http", "https") and host_permitido((o.hostname or "").lower()) and o.netloc.lower() == (host or "").lower()


def login_bloqueado(janela=600, maximo=10):
    with lock:
        agora = time.time()
        _falhas_login[:] = [t for t in _falhas_login if agora - t < janela]
        return len(_falhas_login) >= maximo


def registra_falha_login():
    with lock:
        _falhas_login.append(time.time())
