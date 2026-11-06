"""WhatsApp interno via WAHA: sessão, envio, conversas e eventos recebidos (só leads do CRM)."""
import json, os, re, time
import urllib.error, urllib.parse, urllib.request
from estado import ARQ_CONVERSAS, PORT, WAHA_KEY, WAHA_SESSAO, WAHA_URL, WA_TOKEN, _grava, config, conversas, leads, lock, pendentes_ia, registrar, salvar_leads


def waha(metodo, caminho, corpo=None, timeout=30):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(WAHA_URL + caminho, data=dados, method=metodo, headers={
        "X-Api-Key": WAHA_KEY, "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


def waha_garante_sessao():
    """Cria/inicia a sessão 'default' com o webhook apontando para este painel."""
    # o WAHA roda no Docker: de dentro do container o painel é host.docker.internal
    base = os.environ.get("WAHA_HOOK_BASE", f"http://host.docker.internal:{PORT}")
    webhook = {"url": f"{base}/api/wa/evento", "events": ["message.any", "session.status"],
               "customHeaders": [{"name": "X-WA-Token", "value": WA_TOKEN}]}
    cfg = {"webhooks": [webhook], "ignore": {"status": True, "groups": True, "channels": True, "broadcast": True}}
    try:
        s = waha("GET", f"/api/sessions/{WAHA_SESSAO}")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        return waha("POST", "/api/sessions", {"name": WAHA_SESSAO, "start": True, "config": cfg})
    waha("PUT", f"/api/sessions/{WAHA_SESSAO}", {"name": WAHA_SESSAO, "config": cfg})
    if s.get("status") == "STOPPED":
        waha("POST", f"/api/sessions/{WAHA_SESSAO}/start")
    elif s.get("status") == "FAILED":  # normalmente o QR venceu sem ninguém escanear
        waha("POST", f"/api/sessions/{WAHA_SESSAO}/restart")
    return s


def wa_status():
    out = {"servico": False, "conexao": "desligado", "qr": None, "numero": None, "nome": None, "erro": None}
    try:
        s = waha("GET", f"/api/sessions/{WAHA_SESSAO}", timeout=8)
    except urllib.error.HTTPError as e:
        out.update(servico=True, conexao="sem_sessao" if e.code == 404 else "erro")
        return out
    except Exception as e:
        out["erro"] = f"Serviço de WhatsApp fora do ar ({e})"
        return out
    st = s.get("status")
    out.update(servico=True, conexao={"WORKING": "conectado", "SCAN_QR_CODE": "qr", "STARTING": "iniciando",
                                      "FAILED": "erro", "STOPPED": "parado"}.get(st, (st or "").lower()))
    me = s.get("me") or {}
    out.update(numero=re.sub(r"\D", "", (me.get("id") or "").split("@")[0]) or None, nome=me.get("pushName"))
    if st == "SCAN_QR_CODE":
        try:
            q = waha("GET", f"/api/{WAHA_SESSAO}/auth/qr?format=image", timeout=10)
            out["qr"] = f"data:{q.get('mimetype', 'image/png')};base64,{q.get('data', '')}"
        except Exception:
            pass
    return out


def chave_num(d, internacional=False):
    """Número -> chave de comparação: DDD + 8 últimos dígitos (ignora 55 e o 9º dígito).

    internacional=True (números vindos do WhatsApp, sempre com DDI): só aceita DDI 55, senão um +7 99…
    da Rússia viraria o DDD 79 de um lead."""
    d = re.sub(r"\D", "", d or "")
    if internacional and not (d.startswith("55") and len(d) in (12, 13)):
        return ""
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11 and d[2] == "9":
        d = d[:2] + d[3:]
    return d if len(d) == 10 else ""


def lead_por_numero(numero, internacional=False):
    """Só números exatos que já estão no CRM (WhatsApp ou telefone do lead). Senão None."""
    k = chave_num(numero, internacional)
    if not k:
        return None
    with lock:
        for l in leads.values():
            if k in (chave_num(l.get("whatsapp")), chave_num(l.get("tel_digitos"))):
                return l
    return None


def numero_bloqueado(numero):
    """Opt-out vale pelo número, não pelo registro: um lead duplicado com o mesmo telefone também fica de fora."""
    k = chave_num(numero)
    with lock:
        return bool(k) and any(l.get("optout") and k in (chave_num(l.get("whatsapp")), chave_num(l.get("tel_digitos")))
                               for l in leads.values())


def salvar_conversas():
    with lock:
        _grava(ARQ_CONVERSAS, conversas)


def conversa_de(numero, lead):
    with lock:
        if lead.get("_excluido"):
            raise ValueError("Lead excluído.")
        c = conversas.get(numero)
        if not c:
            c = conversas[numero] = {"numero": numero, "lead_id": lead["id"], "msgs": [], "nao_lidas": 0,
                                     "ia": bool(config["agente"].get("auto_responder")), "criado_em": time.time()}
        c["lead_id"] = lead["id"]
        return c


def _add_msg(c, de, txt, mid=None, t=None):
    with lock:
        if mid and any(m.get("id") == mid for m in c["msgs"][-200:]):
            return False
        c["msgs"].append({"id": mid, "t": t or time.time(), "de": de, "txt": txt})
        c["msgs"] = c["msgs"][-500:]
        c["ultima_em"] = time.time()
        return True


def wa_verifica(numero):
    r = waha("GET", f"/api/contacts/check-exists?session={WAHA_SESSAO}&phone={re.sub(r'[^0-9]', '', numero)}")
    return r.get("chatId") if r.get("numberExists") else None


def wa_enviar(lead, texto, de="eu", numero=None):
    """Envia pelo WhatsApp interno, registra na conversa e no histórico do lead, move o funil."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Mensagem vazia.")
    proprios = {chave_num(lead.get("whatsapp")), chave_num(lead.get("tel_digitos"))} - {""}
    numero = re.sub(r"\D", "", numero or lead.get("whatsapp") or lead.get("tel_digitos") or "")
    if not lead_por_numero(numero) or chave_num(numero) not in proprios:
        raise ValueError("Só envio para o número do próprio lead do CRM.")
    if lead.get("optout") or numero_bloqueado(numero):
        raise ValueError("Esse número pediu para não receber mensagens.")
    chat = wa_verifica(numero)
    if not chat:
        with lock:
            lead["sem_whatsapp"] = True
        raise ValueError("Esse número não tem WhatsApp.")
    try:  # "digitando…" proporcional ao texto: parece gente e reduz risco de bloqueio
        waha("POST", "/api/startTyping", {"session": WAHA_SESSAO, "chatId": chat})
        time.sleep(min(8, 1.2 + len(texto) * 0.035))
        waha("POST", "/api/stopTyping", {"session": WAHA_SESSAO, "chatId": chat})
    except Exception:
        pass
    r = waha("POST", "/api/sendText", {"session": WAHA_SESSAO, "chatId": chat, "text": texto[:4000]})
    mid = r.get("id") if isinstance(r.get("id"), str) else (r.get("id") or {}).get("_serialized") or r.get("key", {}).get("id")
    num_real = re.sub(r"\D", "", chat.split("@")[0]) if chat.endswith("@c.us") else numero
    c = conversa_de(num_real, lead)
    with lock:
        _add_msg(c, de, texto, mid)
        c.setdefault("enviados_ids", []).append(mid)
        c["enviados_ids"] = c["enviados_ids"][-200:]
        registrar(lead, "whatsapp", {"eu": "Mensagem enviada pelo WhatsApp interno", "ia": "IA respondeu no WhatsApp",
                                     "auto": "Primeira mensagem enviada automaticamente",
                                     "followup": "Follow-up enviado automaticamente"}.get(de, "WhatsApp"))
        if lead["status"] == "novo":
            lead["status"] = "contatado"
            registrar(lead, "status", "Status: Contatado")
    salvar_conversas(); salvar_leads()
    return c


PARAR_RE = re.compile(r"\b(sair|parar|pare|remover|remova|descadastr\w*|n[aã]o tenho interesse|n[aã]o quero|"
                      r"n[aã]o me (mande|envie|chame)|stop)\b", re.I)


def _numero_evento(p):
    chat = p.get("to") if p.get("fromMe") else p.get("from")
    chat = chat or ""
    if chat.endswith("@lid"):
        alt = (p.get("_data") or {}).get("key", {}).get("remoteJidAlt") or ""
        if alt.endswith("@s.whatsapp.net"):
            return re.sub(r"\D", "", alt.split("@")[0])
        try:
            r = waha("GET", f"/api/{WAHA_SESSAO}/lids/{urllib.parse.quote(chat)}", timeout=10)
            return re.sub(r"\D", "", (r.get("pn") or "").split("@")[0])
        except Exception:
            return ""
    if chat.endswith(("@c.us", "@s.whatsapp.net")):
        return re.sub(r"\D", "", chat.split("@")[0])
    return ""  # grupos, status, canais, broadcast: nunca entram


def wa_evento(ev):
    if ev.get("event") != "message.any":
        return
    p = ev.get("payload") or {}
    texto = (p.get("body") or "").strip() or ("[mídia]" if p.get("hasMedia") else "")
    numero = _numero_evento(p)
    if not numero or not texto:
        return
    with lock:
        lead = lead_por_numero(numero, internacional=True)
        if not lead:
            return  # conversa pessoal / número fora do CRM: ignorada, nada é salvo
        c = conversa_de(numero, lead)
    mid = p.get("id")
    if p.get("fromMe"):
        if mid in (c.get("enviados_ids") or []):
            return  # eco de algo que o próprio painel mandou
        if _add_msg(c, "eu", texto, mid, p.get("timestamp")):
            with lock:
                c["ia"] = False  # você respondeu pelo celular: a IA sai dessa conversa
                c["ia_motivo"] = "Você respondeu pelo celular"
        salvar_conversas()
        return
    if not _add_msg(c, "lead", texto, mid, p.get("timestamp")):
        return
    with lock:
        if lead.get("_excluido"):
            return
        c["nao_lidas"] = c.get("nao_lidas", 0) + 1
        registrar(lead, "resposta", f"Respondeu no WhatsApp: {texto[:120]}")
        if lead["status"] in ("novo", "contatado"):
            lead["status"] = "respondeu"
            registrar(lead, "status", "Status: Respondeu")
        if PARAR_RE.search(texto) and len(texto) < 80:
            lead["optout"] = True
            c["ia"], c["ia_motivo"] = False, "Pediu para não receber mensagens"
            lead["status"] = "descartado"
            registrar(lead, "status", "Status: Descartado (pediu para parar)")
        elif c.get("ia") and config["agente"].get("auto_responder"):
            # espera um pouco: a pessoa costuma mandar várias mensagens seguidas
            pendentes_ia[numero] = time.time() + int(config["agente"].get("espera_s", 25))
    salvar_conversas(); salvar_leads()
