#!/usr/bin/env python3
"""Painel de prospecção (pt-BR) para o Google Maps Scraper Kit.

Servidor local, só biblioteca padrão. Serve o sistema em http://localhost:8090 e conversa com o
motor (docker compose) em http://localhost:8080. As buscas rodam UMA DE CADA VEZ numa fila,
de propósito: buscas paralelas contra o Google aumentam a chance de bloqueio.

Dados (tudo local, em painel/dados/):
  leads.json       base única de leads (CRM), chave = place_id do Google
  buscas/<id>.json cada busca, com os ids dos leads que ela trouxe
  config.json      modelos de mensagem do WhatsApp

    python3 painel/server.py
"""
import hmac, json, os, re, socket, sys, threading, time
import urllib.error, urllib.parse, urllib.request, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from roteiros import CAMPANHAS_PADRAO, FOLLOWUP_PADRAO, ROTEIROS_VERSAO
from estado import API_TOKEN, ARQ_AGENDA, ARQ_CONFIG, ARQ_CONVERSAS, ARQ_LEADS, ARQ_SESSOES, CONFIG_PADRAO, DADOS, DIR_BUSCAS, HERE, NOME_STATUS, PORT, STATUS_LEAD, TAMANHOS, _le, agenda_dados, buscas, config, conversas, fila, fila_cond, leads, lock, registrar, salvar_busca, salvar_config, salvar_leads, sessoes
from normaliza import mesclar_leads, municipios
from campanhas import SEGMENTOS
from visoes import lead_publico, motor_ok, painel_inicio, resumo_busca
from whatsapp import waha_garante_sessao
from disparo import disparador, respondedor
from buscas import trabalhador
from estado import kit
import lixeira
import rotas_atendimento
import rotas_lixeira
import rotas_scraper
import rotas_auth
from seguranca_http import (CABECALHOS_SEGURANCA, LIMITE_CORPO, host_permitido, nome_host, origem_permitida)


def migra_roteiros():
    """Textos padrão novos (ROTEIROS_VERSAO): troca estratégia e variações, mantém o que você ligou/desligou e
    guarda os textos anteriores em config["roteiros_anteriores"], para nada se perder."""
    config["roteiros_anteriores"] = {"versao": config.get("roteiros_versao", 0),
                                     "campanhas": json.loads(json.dumps(config["campanhas"])),
                                     "followup": json.loads(json.dumps(config["followup"]))}
    for sid, padrao in CAMPANHAS_PADRAO.items():
        config["campanhas"][sid].update(estrategia=padrao["estrategia"], variantes=list(padrao["variantes"]))
    ativo = config["followup"].get("ativo", True)
    config["followup"] = {**json.loads(json.dumps(FOLLOWUP_PADRAO)), "ativo": ativo}
    config["roteiros_versao"] = ROTEIROS_VERSAO
    salvar_config()


def carregar():
    leads.update(_le(ARQ_LEADS, {}))
    config.update(_le(ARQ_CONFIG, None) or json.loads(json.dumps(CONFIG_PADRAO)))
    for chave in ("agente", "agenda", "auto_envio"):  # config de versões antigas: completa com os padrões
        config[chave] = {**CONFIG_PADRAO[chave], **(config.get(chave) or {})}
    camp = config.get("campanhas") or {}
    config["campanhas"] = {sid: {**json.loads(json.dumps(CAMPANHAS_PADRAO[sid])), **(camp.get(sid) or {})} for sid in SEGMENTOS}
    config["followup"] = {**json.loads(json.dumps(FOLLOWUP_PADRAO)), **(config.get("followup") or {})}
    if config.get("roteiros_versao", 0) < ROTEIROS_VERSAO:
        migra_roteiros()
    conversas.update(_le(ARQ_CONVERSAS, {}))
    agenda_dados.update(_le(ARQ_AGENDA, {"reservas": []}))
    for nome in os.listdir(DIR_BUSCAS):
        if nome.endswith(".json"):
            b = _le(os.path.join(DIR_BUSCAS, nome), None)
            if b:
                buscas[b["id"]] = b
    # migra o formato antigo (uma busca por arquivo em dados/, com os leads dentro)
    for nome in os.listdir(DADOS):
        caminho = os.path.join(DADOS, nome)
        if not nome.endswith(".json") or caminho in (ARQ_LEADS, ARQ_CONFIG):
            continue
        b = _le(caminho, None)
        if not b or "parametros" not in b:
            continue
        antigos = b.pop("leads", None) or []
        b["lead_ids"] = mesclar_leads(b, antigos)
        buscas[b["id"]] = b
        salvar_busca(b)
        os.remove(caminho)
    for b in buscas.values():
        if b.get("estado") in ("na_fila", "rodando"):  # servidor caiu no meio: recoloca na fila
            b["estado"], b["etapa"] = "na_fila", "Aguardando (retomada após reinício)"
            fila.append(b["id"])
    fila.sort(key=lambda i: buscas[i]["criado_em"])
    lixeira.limpar_vencidas()  # o que está na lixeira há mais de 30 dias é apagado
    salvar_leads()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _envia(self, code, corpo, tipo="application/json; charset=utf-8"):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(code)
        for k, v in getattr(self, "_extra", []):
            self.send_header(k, v)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        for k, v in CABECALHOS_SEGURANCA:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self):
        n = min(int(self.headers.get("Content-Length") or 0), LIMITE_CORPO)  # _guarda já recusa acima disso
        return json.loads(self.rfile.read(n) or b"{}")

    def _rota(self):
        return urllib.parse.urlparse(self.path).path

    # ── autenticação: cookie de sessão (navegador) ou X-Prospecta-Token (MCP/scripts) ──
    def _cookie(self):
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == "prospecta":
                return v
        return ""

    def _autorizado(self):
        tok = self.headers.get("X-Prospecta-Token")
        if tok and hmac.compare_digest(tok, API_TOKEN):
            return True
        c = self._cookie()
        with lock:
            return bool(c) and sessoes.get(c, 0) > time.time()

    def _publico(self, metodo, path):
        return (path in ("/", "/index.html", "/favicon.ico") or path.startswith(("/api/auth/", "/static/"))
                or (metodo == "POST" and path == "/api/wa/evento"))

    def _token_ok(self):
        tok = self.headers.get("X-Prospecta-Token")
        return bool(tok) and hmac.compare_digest(tok, API_TOKEN)

    def _guarda(self, metodo):
        """Barreiras antes de qualquer rota. Devolve True se já respondeu (bloqueou)."""
        path = self._rota()
        webhook = metodo == "POST" and path == "/api/wa/evento"
        # DNS rebinding: só aceita os nomes do próprio computador (e o do Tailscale); o container do WAHA
        # chega como host.docker.internal, só no webhook
        if not host_permitido(nome_host(self.headers.get("Host")), webhook):
            self._envia(403, {"erro": "Host não permitido."})
            return True
        if int(self.headers.get("Content-Length") or 0) > LIMITE_CORPO:
            self._envia(413, {"erro": "Pedido grande demais."})
            return True
        # CSRF a partir de outra porta do localhost (SameSite não separa portas): pedido do navegador que
        # muda algo precisa vir de origem permitida e em JSON (form/text-plain sem preflight não passa)
        if metodo != "GET" and not webhook and not self._token_ok():
            origem = self.headers.get("Origin")
            json_ok = (self.headers.get("Content-Type") or "").lower().startswith("application/json")
            if not json_ok or not origem or not origem_permitida(origem, self.headers.get("Host")):
                self._envia(403, {"erro": "Origem não permitida."})
                return True
        if self._publico(metodo, path) or self._autorizado():
            return False
        self._envia(401, {"erro": "Faça login.", "login": True})
        return True

    def _auth(self, metodo, path):
        return rotas_auth.atender(self, metodo, path)

    TIPOS = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
             ".png": "image/png", ".webp": "image/webp"}

    def _estatico(self, path):
        """Arquivos de painel/static/ (CSS e JS da tela). Bloqueia ../ e qualquer coisa fora da pasta."""
        base = os.path.realpath(os.path.join(HERE, "static"))
        alvo = os.path.realpath(os.path.join(base, urllib.parse.unquote(path[len("/static/"):])))
        tipo = self.TIPOS.get(os.path.splitext(alvo)[1].lower())
        if not alvo.startswith(base + os.sep) or not tipo or not os.path.isfile(alvo):
            return self._envia(404, {"erro": "não encontrado"})
        with open(alvo, "rb") as f:
            return self._envia(200, f.read(), tipo)

    # ── atendimento: WhatsApp, conversas, agente, agenda ──
    def _atendimento(self, metodo, path):
        return rotas_scraper.atender(self, metodo, path) or rotas_lixeira.atender(self, metodo, path) or rotas_atendimento.atender(self, metodo, path)

    def do_GET(self):
        if self._guarda("GET"):
            return
        path = self._rota()
        if path.startswith("/api/auth/"):
            return self._auth("GET", path)
        try:
            if self._atendimento("GET", path):
                return
        except Exception as e:
            return self._envia(502, {"erro": str(e)})
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._envia(200, f.read(), "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self._estatico(path)
        if path == "/api/status":
            return self._envia(200, {"motor": motor_ok(), "fila": len(fila), "automacoes_pausadas": "--sem-automacoes" in sys.argv})
        if path == "/api/municipios":
            return self._envia(200, [{k: m[k] for k in ("n", "uf", "ddd", "cap")} for m in municipios()])
        if path == "/api/inicio":
            return self._envia(200, painel_inicio())
        if path == "/api/config":
            return self._envia(200, config)
        m = re.fullmatch(r"/api/buscas/([\w-]+)", path)
        if m and m.group(1) in buscas:
            with lock:
                b = buscas[m.group(1)]
                return self._envia(200, resumo_busca(b) | {"lead_ids": b.get("lead_ids", [])})
        if path == "/api/leads":
            with lock:
                return self._envia(200, [lead_publico(l) for l in leads.values()])
        m = re.fullmatch(r"/api/leads/([\w-]+)", path)
        if m and m.group(1) in leads:
            with lock:
                return self._envia(200, leads[m.group(1)])
        self._envia(404, {"erro": "não encontrado"})

    def do_POST(self):
        if self._guarda("POST"):
            return
        path = self._rota()
        if path.startswith("/api/auth/"):
            return self._auth("POST", path)
        try:
            if self._atendimento("POST", path):
                return
        except Exception as e:
            return self._envia(502, {"erro": str(e)})
        if path == "/api/buscas":
            d = self._corpo()
            nichos = [n.strip() for n in re.split(r"[\n,;]", d.get("nichos", "")) if n.strip()][:10]
            if not nichos or not d.get("cidade") or not d.get("uf"):
                return self._envia(400, {"erro": "Informe o nicho e a cidade."})
            if d.get("tamanho") not in TAMANHOS:
                d["tamanho"] = "padrao"
            bid = uuid.uuid4().hex
            b = {"id": bid, "criado_em": time.time(), "estado": "na_fila", "etapa": "Na fila",
                 "parametros": {"nichos": nichos, "cidade": d["cidade"].strip(), "uf": d["uf"].strip().upper(),
                                "bairro": (d.get("bairro") or "").strip(), "tamanho": d["tamanho"],
                                "redes": bool(d.get("redes", True))},
                 "jobs_motor": [], "avisos": [], "lead_ids": [], "progresso": None}
            with fila_cond:
                buscas[bid] = b
                fila.append(bid)
                fila_cond.notify()
            salvar_busca(b)
            return self._envia(201, resumo_busca(b))
        m = re.fullmatch(r"/api/buscas/([\w-]+)/(cancelar|repetir)", path)
        if m and m.group(1) in buscas:
            b = buscas[m.group(1)]
            if m.group(2) == "repetir" and b.get("origem") == "sithia_scraper":
                return self._envia(409, {"erro": "Refaça essa busca na tela Scraper com mapa."})
            with fila_cond:
                if m.group(2) == "cancelar":
                    b["cancelar"] = True
                    if b["id"] in fila:
                        fila.remove(b["id"])
                        b["estado"], b["etapa"] = "cancelada", "Cancelada"
                elif b["estado"] not in ("rodando", "na_fila"):
                    b.update(estado="na_fila", etapa="Na fila", cancelar=False, avisos=[], progresso=None)
                    fila.append(b["id"])
                    fila_cond.notify()
            salvar_busca(b)
            return self._envia(200, resumo_busca(b))
        m = re.fullmatch(r"/api/leads/([\w-]+)/evento", path)
        if m and m.group(1) in leads:
            d, l = self._corpo(), leads[m.group(1)]
            with lock:
                tipo = d.get("tipo") if d.get("tipo") in ("whatsapp", "ligacao", "email", "nota") else "nota"
                txt = str(d.get("txt") or "")[:2000]
                if tipo == "nota" and not txt.strip():
                    return self._envia(400, {"erro": "Escreva a anotação."})
                registrar(l, tipo, txt)
                if tipo in ("whatsapp", "ligacao", "email") and l["status"] == "novo" and config.get("auto_contatado", True):
                    l["status"] = "contatado"
                    registrar(l, "status", "Status: Contatado")
            salvar_leads()
            return self._envia(200, l)
        if path == "/api/leads/lote":
            d = self._corpo()
            if d.get("status") not in STATUS_LEAD:
                return self._envia(400, {"erro": "status inválido"})
            n = 0
            with lock:
                for lid in d.get("ids", []):
                    l = leads.get(lid)
                    if l and l["status"] != d["status"]:
                        l["status"] = d["status"]
                        registrar(l, "status", f"Status: {NOME_STATUS[d['status']]}")
                        n += 1
            salvar_leads()
            return self._envia(200, {"alterados": n})
        self._envia(404, {"erro": "não encontrado"})

    def do_PATCH(self):
        if self._guarda("PATCH"):
            return
        m = re.fullmatch(r"/api/leads/([\w-]+)", self._rota())
        if not m or m.group(1) not in leads:
            return self._envia(404, {"erro": "não encontrado"})
        d, l = self._corpo(), leads[m.group(1)]
        with lock:
            if d.get("status") in STATUS_LEAD and d["status"] != l["status"]:
                l["status"] = d["status"]
                registrar(l, "status", f"Status: {NOME_STATUS[d['status']]}")
            if "obs" in d:
                l["obs"] = str(d["obs"])[:2000]
                l["atualizado_em"] = time.time()
        salvar_leads()
        self._envia(200, l)

    def do_PUT(self):
        if self._guarda("PUT"):
            return
        try:
            if self._atendimento("PUT", self._rota()):
                return
        except Exception as e:
            return self._envia(502, {"erro": str(e)})
        if self._rota() != "/api/config":
            return self._envia(404, {"erro": "não encontrado"})
        d = self._corpo()
        tpls = [{"id": str(t.get("id") or uuid.uuid4().hex[:8]), "nome": str(t.get("nome") or "Sem nome")[:80],
                 "texto": str(t.get("texto") or "")[:2000]} for t in d.get("templates", [])][:30]
        with lock:
            config["templates"] = tpls or CONFIG_PADRAO["templates"]
            ids = [t["id"] for t in config["templates"]]
            config["padrao"] = d.get("padrao") if d.get("padrao") in ids else ids[0]
            config["auto_contatado"] = bool(d.get("auto_contatado", True))
        salvar_config()
        self._envia(200, config)

    def do_DELETE(self):
        if self._guarda("DELETE"):
            return
        try:
            if self._atendimento("DELETE", self._rota()):
                return
        except Exception as e:
            return self._envia(502, {"erro": str(e)})
        self._envia(404, {"erro": "não encontrado"})


def main():
    carregar()
    sessoes.update(_le(ARQ_SESSOES, {}))
    threading.Thread(target=trabalhador, daemon=True).start()
    if "--sem-automacoes" not in sys.argv:
        threading.Thread(target=disparador, daemon=True).start()
        threading.Thread(target=respondedor, daemon=True).start()
    def _liga_whatsapp():  # sessão já pareada volta sozinha quando o WAHA sobe
        for _ in range(30):
            try:
                waha_garante_sessao()
                return
            except Exception:
                time.sleep(10)
    threading.Thread(target=_liga_whatsapp, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    try:  # o navegador pode resolver "localhost" como ::1 (IPv6); continua só local
        class H6(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        threading.Thread(target=H6(("::1", PORT), H).serve_forever, daemon=True).start()
    except OSError:
        pass
    url = f"http://localhost:{PORT}"
    print(f"Painel de prospecção rodando em {url}  (Ctrl+C para parar)")
    if not motor_ok():
        print("⚠  Motor fora do ar em", kit.BASE, "— abra o Docker e rode: docker compose up -d")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
