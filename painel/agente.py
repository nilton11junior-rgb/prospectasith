"""Agente de atendimento IA: Claude Code da assinatura (ou chave de API), prompts e ações da conversa."""
import json, os, re, shutil, subprocess
import urllib.error, urllib.parse, urllib.request
from datetime import datetime
from roteiros import SISTEMA_IA
from estado import DADOS, NOME_STATUS, config, conversas, leads, lock, registrar, salvar_leads
from campanhas import SEGMENTOS, escolhe_variante, preenche, segmento_de, tem_instagram, tem_site
from agenda import BR, fmt_slot, proximos_slots, reservar
from whatsapp import salvar_conversas, wa_enviar


# pasta vazia FORA do projeto: dentro dele o Claude Code acharia .mcp.json/.claude e travaria pedindo aprovação
DIR_AGENTE = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "prospecta-agente")


os.makedirs(DIR_AGENTE, exist_ok=True)


ARQ_CHAVE = os.path.join(DADOS, "anthropic_key")  # opcional: com chave a IA responde em segundos


MODELOS_API = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}


def chave_api():
    try:
        with open(ARQ_CHAVE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def chama_api(sistema, prompt, modelo):
    corpo = {"model": MODELOS_API.get(modelo, MODELOS_API["sonnet"]), "max_tokens": 1024, "system": sistema,
             "messages": [{"role": "user", "content": prompt}]}
    r = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(corpo).encode(), method="POST",
                               headers={"x-api-key": chave_api(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            res = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API da Anthropic recusou ({e.code}): {e.read().decode(errors='replace')[:200]}")
    return "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")


def claude_bin():
    for c in (os.environ.get("CLAUDE_BIN"), shutil.which("claude"),
              os.path.expanduser(r"~\.local\bin\claude.exe"), os.path.expanduser("~/.local/bin/claude")):
        if c and os.path.exists(c):
            return c
    return None


def chama_claude(sistema, prompt, modelo=None, timeout=300):
    if chave_api():
        return chama_api(sistema, prompt, modelo or config["agente"].get("modelo") or "sonnet")
    exe = claude_bin()
    if not exe:
        raise RuntimeError("Claude Code não encontrado. Instale e faça login (claude) neste computador.")
    cmd = [exe, "-p", "--output-format", "json", "--model", modelo or config["agente"].get("modelo") or "sonnet",
           "--max-turns", "1", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
           "--setting-sources", "", "--no-session-persistence", "--system-prompt", sistema]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout, cwd=DIR_AGENTE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        res = json.loads(p.stdout)
    except ValueError:
        raise RuntimeError(f"Claude não respondeu: {(p.stderr or p.stdout)[:300]}")
    if res.get("is_error") or res.get("terminal_reason") not in (None, "completed"):
        raise RuntimeError(f"Claude: {str(res.get('result') or res.get('terminal_reason'))[:300]}")
    return res.get("result") or ""


def _json_de(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        raise RuntimeError("A IA não devolveu JSON.")
    return json.loads(m.group(0))


def contexto_lead(l):
    return "\n".join(f"{k}: {v}" for k, v in (
        ("Empresa", l.get("nome")), ("Categoria", l.get("categoria")), ("Cidade", f"{l.get('bairro') or ''} {l.get('cidade') or ''} {l.get('uf') or ''}".strip()),
        ("Tem site", "sim" if tem_site(l) else "não"), ("Tem Instagram", "sim" if tem_instagram(l) else "não encontrado"),
        ("Nota no Google", l.get("nota") or "—"),
        ("Avaliações", l.get("avaliacoes") or 0), ("Etapa do funil", NOME_STATUS.get(l.get("status"), l.get("status"))),
        ("Anotações", l.get("obs") or "—")))


def prompt_conversa(l, c, extra=""):
    ag = config["agente"]
    hist = "\n".join(f"[{datetime.fromtimestamp(m['t'], BR).strftime('%d/%m %H:%M')}] "
                     f"{'LEAD' if m['de'] == 'lead' else 'NÓS'}: {m['txt']}" for m in c["msgs"][-30:])
    return (f"BASE DE CONHECIMENTO:\n{ag.get('base') or '(vazia)'}\n\nINSTRUÇÕES DE ABORDAGEM:\n{ag.get('instrucoes') or '(nenhuma)'}\n\n"
            f"DADOS DO LEAD:\n{contexto_lead(l)}\n\n{estrategia_lead(l)}AGORA:{datetime.now(BR).strftime('%A %d/%m/%Y %H:%M')} (Brasília)\n"
            f"HORÁRIOS LIVRES (use o formato exato): {', '.join(proximos_slots()) or 'nenhum — ofereça retornar depois'}\n\n"
            f"CONVERSA ATÉ AGORA:\n{hist or '(nenhuma)'}\n{extra}")


def estrategia_lead(l):
    seg = l.get("segmento_envio") or segmento_de(l) or segmento_de(l, so_ativos=False)
    camp = config.get("campanhas", {}).get(seg or "", {})
    if not seg or not camp.get("estrategia"):
        return ""
    return f"SITUAÇÃO DA EMPRESA: {SEGMENTOS[seg]['nome']}\nESTRATÉGIA PARA ESTE LEAD: {camp['estrategia']}\n\n"


def ia_decide(l, c, extra=""):
    return _json_de(chama_claude(SISTEMA_IA, prompt_conversa(l, c, extra)))


def ia_responder(numero):
    """Gera a resposta da IA para uma conversa e executa a ação (agendar só confirma após reservar)."""
    with lock:
        c = conversas.get(numero)
        l = leads.get(c["lead_id"]) if c else None
    if not c or not l or not c.get("ia") or l.get("optout") or l["status"] in ("descartado", "fechado"):
        return
    if not c["msgs"] or c["msgs"][-1]["de"] != "lead":
        return
    d = ia_decide(l, c)
    acao, msg = d.get("acao") or "nada", (d.get("mensagem") or "").strip()
    if d.get("resumo"):
        with lock:
            registrar(l, "ia", f"IA: {d['resumo'][:200]}")
    if acao == "agendar":
        try:
            reservar(l, (d.get("horario") or "").strip(), "ia")
        except ValueError:
            livres = proximos_slots(3)
            msg = ("Esse horário acabou de ser ocupado 😕 " + (f"Tenho livre {', '.join(fmt_slot(s) for s in livres)}. Qual fica melhor?"
                   if livres else "Vou ver com a equipe um novo horário e já te retorno."))
    elif acao == "humano":
        with lock:
            c["ia"], c["ia_motivo"] = False, "IA passou para atendimento humano"
            registrar(l, "nota", "IA pediu atendimento humano nessa conversa")
    elif acao == "encerrar":
        with lock:
            l["optout"], c["ia"], c["ia_motivo"] = True, False, "Lead encerrou a conversa"
            if l["status"] != "descartado":
                l["status"] = "descartado"
                registrar(l, "status", "Status: Descartado")
    if msg and acao != "nada":
        wa_enviar(l, msg, de="ia", numero=numero)
    salvar_conversas(); salvar_leads()


def primeira_mensagem(l, modo=None):
    """Primeira mensagem conforme o segmento (situação) da empresa: variação do roteiro ou escrita pela IA."""
    modo = modo or config["auto_envio"].get("modo", "template")
    seg = segmento_de(l) or segmento_de(l, so_ativos=False)
    camp = config["campanhas"].get(seg, {}) if seg else {}
    if modo == "ia":
        sistema = ("Você escreve a PRIMEIRA mensagem de prospecção por WhatsApp para uma empresa, em português do Brasil. "
                   "Curta (2 a 3 frases), personalizada com nome/cidade/categoria, educada, sem link, sem parecer spam, "
                   "termina com uma pergunta simples de sim/não. Siga a ESTRATÉGIA DO SEGMENTO e use só a base de conhecimento. "
                   "Responda APENAS {\"mensagem\": \"...\"}.")
        ag = config["agente"]
        p = (f"BASE DE CONHECIMENTO:\n{ag.get('base') or '(vazia)'}\n\nINSTRUÇÕES:\n{ag.get('instrucoes') or ''}\n\n"
             f"SEGMENTO: {SEGMENTOS.get(seg, {}).get('nome', 'geral')}\nESTRATÉGIA DO SEGMENTO: {camp.get('estrategia') or '—'}\n\n"
             f"EXEMPLOS DE TOM (não copie):\n" + "\n".join(f"- {v}" for v in camp.get("variantes", [])[:2]) +
             f"\n\nEMPRESA:\n{contexto_lead(l)}")
        return (_json_de(chama_claude(sistema, p)).get("mensagem") or "").strip()
    variantes = [v for v in camp.get("variantes", []) if v.strip()]
    if not variantes:  # segmento sem roteiro: cai no modelo de mensagem escolhido
        tpl = next((t for t in config["templates"] if t["id"] == config["auto_envio"].get("template")), config["templates"][0])
        variantes = [tpl["texto"]]
    return preenche(escolhe_variante(seg or "geral", variantes), l)
