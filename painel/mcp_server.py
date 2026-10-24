#!/usr/bin/env python3
"""Servidor MCP do Prospecta (stdio, só biblioteca padrão).

Dá ao Claude Code (ou outro cliente MCP) ferramentas para consultar e operar o CRM: leads, buscas,
conversas do WhatsApp interno, agenda e envio de mensagens. Fala com o painel em
http://127.0.0.1:8090 usando o token local de painel/dados/api_token.

Envio de WhatsApp e reservas exigem confirmar=true: o agente precisa mostrar o texto ao usuário
e só confirmar depois do "sim".

    claude mcp add prospecta -- python painel/mcp_server.py
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PROSPECTA_URL", f"http://127.0.0.1:{os.environ.get('PAINEL_PORT', '8090')}")
PROTOCOLO = "2025-06-18"


def token():
    with open(os.path.join(HERE, "dados", "api_token"), encoding="utf-8") as f:
        return f.read().strip()


def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers={
        "X-Prospecta-Token": token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("erro")
        except Exception:
            msg = None
        raise RuntimeError(msg or f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Painel fora do ar em {BASE} ({e.reason}). Abra o Prospeccao.cmd.")


def enxuto(l):
    return {k: l.get(k) for k in ("id", "nome", "categoria", "status", "whatsapp", "telefone", "email", "site",
                                  "bairro", "cidade", "uf", "nota", "avaliacoes", "obs", "reuniao", "optout")}


def t_resumo(a):
    return api("GET", "/api/inicio") | {"whatsapp": api("GET", "/api/wa/status") | {"qr": None}}

def t_listar_leads(a):
    ls = api("GET", "/api/leads")
    q = (a.get("texto") or "").lower()
    ls = [l for l in ls if (not a.get("status") or l["status"] == a["status"])
          and (not a.get("cidade") or (l.get("cidade") or "").lower() == a["cidade"].lower())
          and (not a.get("so_whatsapp") or l.get("whatsapp"))
          and (not q or q in f"{l.get('nome')} {l.get('categoria')} {l.get('bairro')}".lower())]
    lim = int(a.get("limite") or 30)
    return {"total": len(ls), "leads": [enxuto(l) for l in ls[:lim]]}

def t_ver_lead(a):
    return api("GET", f"/api/leads/{urllib.parse.quote(a['lead_id'])}")

def t_nova_busca(a):
    return api("POST", "/api/buscas", {"nichos": a["nichos"], "cidade": a["cidade"], "uf": a["uf"],
                                       "bairro": a.get("bairro", ""), "tamanho": a.get("tamanho", "padrao")})

def t_buscas(a):
    return [{k: b.get(k) for k in ("id", "parametros", "estado", "etapa", "total", "com_whatsapp", "com_email", "sem_site")}
            for b in api("GET", "/api/buscas")[: int(a.get("limite") or 15)]]

def t_mudar_status(a):
    return enxuto(api("PATCH", f"/api/leads/{urllib.parse.quote(a['lead_id'])}", {"status": a["status"]}))

def t_anotar(a):
    return enxuto(api("POST", f"/api/leads/{urllib.parse.quote(a['lead_id'])}/evento", {"tipo": "nota", "txt": a["texto"]}))

def t_conversas(a):
    return api("GET", "/api/conversas")[: int(a.get("limite") or 20)]

def t_ver_conversa(a):
    c = api("GET", f"/api/conversas/{a['numero']}")
    c["lead"] = enxuto(c.get("lead") or {})
    return c

def t_enviar(a):
    if not a.get("confirmar"):
        return {"aviso": "Nada foi enviado. Mostre o texto ao usuário e chame de novo com confirmar=true depois do sim.",
                "texto": a.get("texto")}
    return {"ok": True, "numero": api("POST", "/api/wa/enviar", {"lead_id": a.get("lead_id"), "numero": a.get("numero"),
                                                                  "texto": a["texto"]})["conversa"]["numero"]}

def t_primeira(a):
    return api("POST", "/api/agente/primeira", {"lead_id": a["lead_id"], "modo": a.get("modo", "template")})

def t_ia_conversa(a):
    return api("POST", f"/api/conversas/{a['numero']}/ia", {"ativa": bool(a["ativa"])})

def t_horarios(a):
    q = f"?dia={a['dia']}" if a.get("dia") else ""
    r = api("GET", f"/api/agenda{q}")
    return {"dia": r["dia"], "livres": r["slots"], "compromissos": r["reservas"]}

def t_agendar(a):
    if not a.get("confirmar"):
        return {"aviso": "Nada foi reservado. Confirme com o usuário e chame de novo com confirmar=true."}
    return api("POST", "/api/agenda/reservar", {"lead_id": a["lead_id"], "inicio": a["inicio"]})

def t_disparo(a):
    r = api("GET", "/api/agente")
    if "ativo" in a:
        if a["ativo"] and not a.get("confirmar"):
            return {"aviso": "Ligar o disparo automático envia mensagens sozinho. Confirme com o usuário e use confirmar=true.",
                    "na_fila": r["elegiveis"], "config": r["auto_envio"]}
        api("PUT", "/api/agente", {"auto_envio": {"ativo": bool(a["ativo"])}})
        r = api("GET", "/api/agente")
    return {"auto_envio": r["auto_envio"], "enviados_hoje": r["envios"].get("n"), "na_fila": r["elegiveis"],
            "dentro_do_horario": r["janela"], "ultimo_erro": r["envios"].get("ultimo_erro")}


S = {"type": "string"}
STATUS = {"type": "string", "enum": ["novo", "contatado", "respondeu", "reuniao", "fechado", "descartado"]}
FERRAMENTAS = [
    ("resumo", "Resumo do CRM: totais, funil, cidades, eventos recentes e conexão do WhatsApp.", {}, [], t_resumo),
    ("listar_leads", "Lista leads com filtros.", {"status": STATUS, "cidade": S, "texto": S, "so_whatsapp": {"type": "boolean"},
                                                 "limite": {"type": "integer"}}, [], t_listar_leads),
    ("ver_lead", "Ficha completa de um lead, com histórico.", {"lead_id": S}, ["lead_id"], t_ver_lead),
    ("nova_busca", "Enfileira uma busca no Google Maps (nichos separados por vírgula).",
     {"nichos": S, "cidade": S, "uf": S, "bairro": S, "tamanho": {"type": "string", "enum": ["rapida", "padrao", "completa", "cidade"]}},
     ["nichos", "cidade", "uf"], t_nova_busca),
    ("buscas", "Buscas recentes e o andamento delas.", {"limite": {"type": "integer"}}, [], t_buscas),
    ("mudar_status", "Move o lead de etapa no funil.", {"lead_id": S, "status": STATUS}, ["lead_id", "status"], t_mudar_status),
    ("anotar", "Adiciona uma anotação ao lead.", {"lead_id": S, "texto": S}, ["lead_id", "texto"], t_anotar),
    ("conversas", "Conversas do WhatsApp interno (só leads do CRM).", {"limite": {"type": "integer"}}, [], t_conversas),
    ("ver_conversa", "Mensagens de uma conversa.", {"numero": S}, ["numero"], t_ver_conversa),
    ("gerar_primeira_mensagem", "Gera (sem enviar) a primeira mensagem para um lead.",
     {"lead_id": S, "modo": {"type": "string", "enum": ["template", "ia"]}}, ["lead_id"], t_primeira),
    ("enviar_whatsapp", "Envia uma mensagem pelo WhatsApp interno para um lead do CRM. Exige confirmar=true depois do OK do usuário.",
     {"lead_id": S, "numero": S, "texto": S, "confirmar": {"type": "boolean"}}, ["texto"], t_enviar),
    ("ia_na_conversa", "Liga ou desliga a IA numa conversa.", {"numero": S, "ativa": {"type": "boolean"}}, ["numero", "ativa"], t_ia_conversa),
    ("horarios_livres", "Horários livres da agenda num dia (AAAA-MM-DD) e compromissos.", {"dia": S}, [], t_horarios),
    ("agendar", "Reserva um horário (AAAA-MM-DD HH:MM) para um lead. Exige confirmar=true.",
     {"lead_id": S, "inicio": S, "confirmar": {"type": "boolean"}}, ["lead_id", "inicio"], t_agendar),
    ("disparo_automatico", "Mostra ou liga/desliga o disparo automático da primeira mensagem. Ligar exige confirmar=true.",
     {"ativo": {"type": "boolean"}, "confirmar": {"type": "boolean"}}, [], t_disparo),
]
POR_NOME = {f[0]: f for f in FERRAMENTAS}


def responde(mid, result=None, erro=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if erro:
        msg["error"] = erro
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def trata(req):
    metodo, mid, p = req.get("method"), req.get("id"), req.get("params") or {}
    if metodo == "initialize":
        return responde(mid, {"protocolVersion": p.get("protocolVersion") or PROTOCOLO,
                              "capabilities": {"tools": {}}, "serverInfo": {"name": "prospecta", "version": "1.0.0"},
                              "instructions": "CRM de prospecção local. Nunca envie WhatsApp nem agende sem mostrar ao usuário e receber o OK."})
    if metodo == "tools/list":
        return responde(mid, {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": props, "required": req_}}
                                        for n, d, props, req_, _ in FERRAMENTAS]})
    if metodo == "tools/call":
        f = POR_NOME.get(p.get("name"))
        if not f:
            return responde(mid, erro={"code": -32602, "message": f"ferramenta desconhecida: {p.get('name')}"})
        try:
            out = f[4](p.get("arguments") or {})
            return responde(mid, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=1)}]})
        except Exception as e:
            return responde(mid, {"content": [{"type": "text", "text": f"Erro: {e}"}], "isError": True})
    if metodo == "ping":
        return responde(mid, {})
    if mid is not None:  # notificações (sem id) não têm resposta
        responde(mid, erro={"code": -32601, "message": f"método não suportado: {metodo}"})


def main():
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            trata(json.loads(linha))
        except ValueError:
            responde(None, erro={"code": -32700, "message": "JSON inválido"})


if __name__ == "__main__":
    main()
