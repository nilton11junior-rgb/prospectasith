"""Rotas de login: estado, criar a senha (só no próprio computador), entrar com bloqueio e sair."""
import time
from estado import ARQ_SESSOES, _grava, auth_configurado, confere_senha, define_senha, lock, nova_sessao, sessoes
from seguranca_http import (HOSTS_LOCAIS, host_publico, login_bloqueado,
                            nome_host, registra_falha_login)


def atender(h, metodo, path):
    if path == "/api/auth/estado" and metodo == "GET":
        return h._envia(200, {"configurado": auth_configurado(), "logado": h._autorizado()})
    if metodo != "POST":
        return h._envia(404, {"erro": "não encontrado"})
    d = h._corpo()
    senha = str(d.get("senha") or "")
    atributos_cookie = "; HttpOnly; SameSite=Strict"
    if host_publico(h.headers.get("Host")):
        atributos_cookie += "; Secure"
    if path == "/api/auth/criar":
        if auth_configurado():
            return h._envia(409, {"erro": "A senha já foi criada."})
        # o Tailscale serve também chega por 127.0.0.1: o nome do host separa quem está no computador
        if h.client_address[0] not in ("127.0.0.1", "::1") or nome_host(h.headers.get("Host")) not in HOSTS_LOCAIS:
            return h._envia(403, {"erro": "Crie a senha no próprio computador."})
        if len(senha) < 6:
            return h._envia(400, {"erro": "Use pelo menos 6 caracteres."})
        define_senha(senha)
    elif path == "/api/auth/entrar":
        if login_bloqueado():
            return h._envia(429, {"erro": "Muitas tentativas. Espere alguns minutos."})
        if not confere_senha(senha):
            registra_falha_login()
            time.sleep(1.5)
            return h._envia(401, {"erro": "Senha incorreta."})
    elif path == "/api/auth/sair":
        with lock:
            sessoes.pop(h._cookie(), None)
            _grava(ARQ_SESSOES, sessoes)
        h._extra = [("Set-Cookie", f"prospecta=; Path=/; Max-Age=0{atributos_cookie}")]
        return h._envia(200, {"ok": True})
    else:
        return h._envia(404, {"erro": "não encontrado"})
    h._extra = [("Set-Cookie", f"prospecta={nova_sessao()}; Path=/; Max-Age={30 * 86400}{atributos_cookie}")]
    return h._envia(200, {"ok": True})
