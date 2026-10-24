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
import csv, hashlib, hmac, io, json, os, random, re, secrets, shutil, socket, subprocess, sys, threading, time, unicodedata
import urllib.error, urllib.parse, urllib.request, uuid, webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "scripts"))
import scrape as kit  # noqa: E402  (reaproveita req, grid, dedupe, extração de email/redes)

PORT = int(os.environ.get("PAINEL_PORT", "8090"))
DADOS = os.path.join(HERE, "dados")
DIR_BUSCAS = os.path.join(DADOS, "buscas")
ARQ_LEADS = os.path.join(DADOS, "leads.json")
ARQ_CONFIG = os.path.join(DADOS, "config.json")
os.makedirs(DIR_BUSCAS, exist_ok=True)
UA = kit.UA

TAMANHOS = {  # depth, grid, max_time (s)
    "rapida":   {"depth": 1,  "grid": 0, "max_time": 600},
    "padrao":   {"depth": 5,  "grid": 0, "max_time": 900},
    "completa": {"depth": 10, "grid": 0, "max_time": 1200},
    "cidade":   {"depth": 5,  "grid": 3, "max_time": 900},
}
STATUS_LEAD = ["novo", "contatado", "respondeu", "reuniao", "fechado", "descartado"]
NOME_STATUS = {"novo": "Novo", "contatado": "Contatado", "respondeu": "Respondeu",
               "reuniao": "Reunião marcada", "fechado": "Fechou negócio", "descartado": "Descartado"}
# campos que vêm do Google/site e podem ser atualizados quando o lead aparece de novo numa busca
CAMPOS_CONTATO = ("nome", "categoria", "telefone", "tel_digitos", "tel_tipo", "whatsapp", "whatsapp_origem",
                  "email", "site", "instagram", "facebook", "linkedin", "endereco", "bairro", "cidade", "uf",
                  "cep", "nota", "avaliacoes", "maps", "fechado")

CONFIG_PADRAO = {"templates": [
    {"id": "apresentacao", "nome": "Primeiro contato",
     "texto": "Olá, tudo bem? Encontrei a {nome} no Google Maps aqui em {cidade} e queria conversar rapidinho "
              "sobre uma ideia para trazer mais clientes para vocês. Posso te mandar?"},
    {"id": "sem_site", "nome": "Para quem não tem site",
     "texto": "Oi! Vi a {nome} no Google com ótimas avaliações, mas não encontrei um site de vocês. "
              "Trabalho justamente ajudando {categoria} de {cidade} a aparecer melhor na internet. Posso te mostrar um exemplo?"},
    {"id": "followup", "nome": "Retomar conversa",
     "texto": "Oi, tudo certo? Passando aqui para retomar nossa conversa sobre a {nome}. Conseguiu dar uma olhada?"},
], "padrao": "apresentacao", "auto_contatado": True,
    # agente de atendimento (IA) que responde os leads no WhatsApp interno
    "agente": {"base": "", "instrucoes": "", "auto_responder": False, "modelo": "sonnet", "espera_s": 25},
    # horários livres para reuniões/chamadas (dias: 0=segunda … 6=domingo)
    "agenda": {"dias": [0, 1, 2, 3, 4], "inicio": "09:00", "fim": "18:00", "duracao": 30, "antecedencia_h": 2},
    # disparo automático da primeira mensagem para leads novos com WhatsApp
    "auto_envio": {"ativo": False, "modo": "template", "template": "apresentacao", "limite_dia": 30,
                   "intervalo_min": 120, "intervalo_max": 300, "hora_ini": "09:00", "hora_fim": "18:00",
                   "dias": [0, 1, 2, 3, 4], "buscas": []}}

ARQ_CONVERSAS = os.path.join(DADOS, "conversas.json")
ARQ_AGENDA = os.path.join(DADOS, "agenda.json")

lock = threading.RLock()
buscas = {}          # id -> busca
leads = {}           # id -> lead
config = {}
conversas = {}       # numero (55DDD…) -> conversa do WhatsApp interno com um lead do CRM
agenda_dados = {}    # {"reservas": [...]}
fila = []            # ids de buscas aguardando
fila_cond = threading.Condition(lock)


# ── Persistência ────────────────────────────────────────────────────────────────
def _grava(caminho, obj):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, caminho)

def salvar_busca(b):
    with lock:
        _grava(os.path.join(DIR_BUSCAS, f"{b['id']}.json"), b)

def salvar_leads():
    with lock:
        _grava(ARQ_LEADS, leads)

def salvar_config():
    with lock:
        _grava(ARQ_CONFIG, config)

def _le(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao

def carregar():
    leads.update(_le(ARQ_LEADS, {}))
    config.update(_le(ARQ_CONFIG, None) or json.loads(json.dumps(CONFIG_PADRAO)))
    for chave in ("agente", "agenda", "auto_envio"):  # config de versões antigas: completa com os padrões
        config[chave] = {**CONFIG_PADRAO[chave], **(config.get(chave) or {})}
    camp = config.get("campanhas") or {}
    config["campanhas"] = {sid: {**json.loads(json.dumps(CAMPANHAS_PADRAO[sid])), **(camp.get(sid) or {})} for sid in SEGMENTOS}
    config["followup"] = {**json.loads(json.dumps(FOLLOWUP_PADRAO)), **(config.get("followup") or {})}
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
    salvar_leads()


# ── Geografia ──────────────────────────────────────────────────────────────────
_municipios = None

def municipios():
    """Municípios do IBGE embutidos (painel/municipios.json): [{n, uf, lat, lon, ddd, cap}].
    Fonte: github.com/kelvins/municipios-brasileiros (códigos e coordenadas do IBGE)."""
    global _municipios
    if _municipios is None:
        with open(os.path.join(HERE, "municipios.json"), encoding="utf-8") as f:
            _municipios = json.load(f)
    return _municipios

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower().strip()

def _municipio(cidade, uf):
    alvo = norm(cidade)
    return next((m for m in municipios() if m["uf"] == uf and norm(m["n"]) == alvo), None)

def geocodificar(local):
    """'Bairro, Cidade, UF' -> (lat, lon, bbox) restrito ao Brasil, via OpenStreetMap. None se falhar."""
    q = urllib.parse.urlencode({"format": "json", "limit": 1, "countrycodes": "br", "q": local})
    r = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            hits = json.loads(resp.read())
    except Exception:
        return None
    time.sleep(1)  # política do Nominatim: ~1 req/s
    if not hits:
        return None
    return hits[0]["lat"], hits[0]["lon"], hits[0].get("boundingbox")

def localizar(cidade, uf, bairro=""):
    """Centro da busca. Bairro: OpenStreetMap. Cidade: OpenStreetMap (traz os limites, usados no
    modo 'cidade inteira'), com o centro do IBGE como reserva se o OSM estiver fora do ar."""
    if bairro:
        geo = geocodificar(f"{bairro}, {cidade}, {uf}, Brasil")
        if geo:
            return geo
    geo = geocodificar(f"{cidade}, {uf}, Brasil")
    if geo:
        return geo
    m = _municipio(cidade, uf)
    if not m:
        return None
    d = 0.12  # ~13 km para cada lado: caixa aproximada quando não há limites do OSM
    return str(m["lat"]), str(m["lon"]), [m["lat"] - d, m["lat"] + d, m["lon"] - d, m["lon"] + d]


# ── Normalização brasileira ────────────────────────────────────────────────────
def telefone_br(bruto):
    """-> (digitos_com_55, tipo) onde tipo ∈ celular | fixo | 0800 | ''."""
    d = re.sub(r"\D", "", bruto or "")
    if d.startswith(("0800", "0300", "0500", "0900")):
        return d, "0800"
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if d.startswith("0") and len(d) in (11, 12):  # 0 + DDD (formato de operadora)
        d = d[1:]
    if len(d) == 11 and d[2] == "9":
        return "55" + d, "celular"
    if len(d) == 10:
        return "55" + d, ("celular" if d[2] in "6789" else "fixo")
    return d, ""

def formata_tel(d55):
    d = d55[2:] if d55.startswith("55") else d55
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d55

WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send/?\?phone=|whatsapp\.com/send/?\?phone=|web\.whatsapp\.com/send\?phone=)\+?(\d{10,13})", re.I)

def whatsapp_em(texto):
    for n in WA_RE.findall(texto or ""):
        d, tipo = telefone_br(n)
        if tipo in ("celular", "fixo"):
            return d
    return ""

def _json(s, padrao):
    try:
        return json.loads(s) if s else padrao
    except ValueError:
        return padrao

def id_lead(row):
    if row.get("place_id"):
        return row["place_id"]
    base = f"{row.get('title', '')}|{row.get('address', '')}"
    return "h" + hashlib.sha1(base.encode()).hexdigest()[:20]

def lead_de(row):
    """Linha bruta do motor -> lead enxuto em português."""
    tel_d, tipo = telefone_br(row.get("phone"))
    end = _json(row.get("complete_address"), {}) or {}
    endereco = row.get("address", "")
    titulo = row.get("title", "")
    if titulo and endereco.startswith(titulo + " - "):
        endereco = endereco[len(titulo) + 3:]
    cep = end.get("postal_code") or (re.search(r"\d{5}-?\d{3}", endereco) or [""])[0]
    uf = end.get("state", "")
    m = re.search(r"-\s*([A-Z]{2})\b", endereco)
    if m and (not uf or len(uf) != 2):
        uf = m.group(1)
    try:
        nota = float(row.get("review_rating") or 0)
    except ValueError:
        nota = 0.0
    try:
        avaliacoes = int(float(row.get("review_count") or 0))
    except ValueError:
        avaliacoes = 0
    wa = whatsapp_em(row.get("order_online", "")) or whatsapp_em(row.get("reservations", ""))
    origem = "maps" if wa else ""
    if not wa and tipo == "celular":
        wa, origem = tel_d, "telefone"
    st = (row.get("status") or "").lower()
    return {
        "id": id_lead(row),
        "nome": titulo,
        "categoria": row.get("category", ""),
        "telefone": formata_tel(tel_d) if tipo in ("celular", "fixo") else (row.get("phone") or ""),
        "tel_digitos": tel_d,
        "tel_tipo": tipo,
        "whatsapp": wa,
        "whatsapp_origem": origem,
        "email": row.get("emails", ""),
        "site": row.get("website", ""),
        "instagram": "", "facebook": "", "linkedin": "",
        "endereco": endereco,
        "bairro": end.get("borough", ""),
        "cidade": end.get("city", ""),
        "uf": uf,
        "cep": cep,
        "nota": nota,
        "avaliacoes": avaliacoes,
        "maps": row.get("link", ""),
        "fechado": "permanently" in st or "permanentemente" in st,
    }

def mesclar_leads(busca, novos):
    """Junta leads de uma busca na base. Lead que já existe: atualiza contato, mantém status,
    anotações e histórico. Devolve os ids na ordem da busca."""
    agora, ids = time.time(), []
    with lock:
        for n in novos:
            lid = n.get("id") or id_lead({"place_id": n.get("place_id"), "title": n.get("nome"), "address": n.get("endereco")})
            atual = leads.get(lid)
            if atual:
                for k in CAMPOS_CONTATO:
                    if n.get(k) not in (None, ""):
                        atual[k] = n[k]
                if busca["id"] not in atual["buscas"]:
                    atual["buscas"].append(busca["id"])
            else:
                lead = {k: n.get(k, "") for k in CAMPOS_CONTATO}
                lead.update(id=lid, status=n.get("status") or "novo", obs=n.get("obs", ""),
                            buscas=[busca["id"]], criado_em=agora, atualizado_em=agora, ultimo_contato=None,
                            nicho=", ".join(busca["parametros"]["nichos"]),
                            historico=[{"t": agora, "tipo": "criado",
                                        "txt": f"Encontrado na busca “{', '.join(busca['parametros']['nichos'])}”"}])
                if lead["obs"]:
                    lead["historico"].append({"t": agora, "tipo": "nota", "txt": lead["obs"]})
                leads[lid] = lead
            if lid not in ids:
                ids.append(lid)
    return ids


# ── Enriquecimento a partir do site (emails, WhatsApp, redes) ──────────────────
CONTATO_RE = re.compile(r"contato|fale|sobre|quem-somos|quem_somos|atendimento|contact|about", re.I)
CAMINHOS = ("/contato", "/fale-conosco", "/sobre", "/quem-somos", "/contact")

def links_contato(html, base):
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    host, out = kit._host(base), []
    for href, txt in kit.HREF_RE.findall(html or ""):
        if not CONTATO_RE.search(href + " " + txt):
            continue
        url = urllib.parse.urldefrag(urllib.parse.urljoin(base, href.strip()))[0]
        if url.startswith(("http://", "https://")) and kit._host(url) == host and url not in out:
            out.append(url)
    for p in CAMINHOS:
        url = urllib.parse.urljoin(base, p)
        if len(out) < 3 and url not in out:
            out.append(url)
    return out[:3]

def enriquecer(lead, redes):
    site = lead["site"]
    if not site or any(h in site for h in ("instagram.com", "facebook.com", "wa.me", "whatsapp.com", "linktr.ee")):
        # o "site" é na verdade uma rede social / link de WhatsApp: aproveita direto
        if "instagram.com" in site: lead["instagram"] = site
        elif "facebook.com" in site: lead["facebook"] = site
        wa = whatsapp_em(site)
        if wa: lead["whatsapp"], lead["whatsapp_origem"] = wa, "site"
        return
    home = kit._fetch_cached(site)
    if not home:
        return
    wa = whatsapp_em(home)
    if wa and (not lead["whatsapp"] or lead["whatsapp_origem"] == "telefone"):
        lead["whatsapp"], lead["whatsapp_origem"] = wa, "site"
    if redes:
        for k, v in kit._find_socials(home).items():
            lead[k] = lead[k] or v
    if not lead["email"]:
        achados = kit.extract_emails(home, site)
        if not achados:
            paginas = "".join(kit._fetch_html(u, timeout=8) for u in links_contato(home, site))
            achados = kit.extract_emails(paginas, site)
            if not lead["whatsapp"]:
                wa = whatsapp_em(paginas)
                if wa: lead["whatsapp"], lead["whatsapp_origem"] = wa, "site"
        lead["email"] = ", ".join(achados)


# ── Execução das buscas ────────────────────────────────────────────────────────
class Cancelada(Exception):
    pass

def atualizar(b, **kw):
    with lock:
        b.update(kw)
        b["atualizado_em"] = time.time()

def _baixar(jid):
    _, raw = kit.req("GET", f"/api/v1/jobs/{jid}/download")
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))

def job_reaproveitavel(jid):
    """Job do motor de uma tentativa anterior que ainda existe e não falhou: acompanha ele em vez
    de raspar tudo de novo (ex.: o painel desistiu por tempo, mas o motor continuou trabalhando)."""
    try:
        _, raw = kit.req("GET", f"/api/v1/jobs/{jid}")
        return json.loads(raw).get("Status") not in (None, "failed")
    except Exception:
        return False

def rodar_job(b, corpo, rotulo, jid=None):
    if not jid:
        _, raw = kit.req("POST", "/api/v1/jobs", corpo)
        jid = json.loads(raw).get("id")
        if not jid:
            raise RuntimeError("O motor não devolveu id do job.")
        with lock:
            b["jobs_motor"].append(jid)
    inicio = time.time()
    # o binário do motor no Windows às vezes termina a raspagem e fica preso em "working":
    # se o CSV já tem linhas e não cresce há 3 min, considera pronto
    ultima_checagem, linhas_vistas, parado_desde = inicio, 0, None
    while True:
        if b.get("cancelar"):
            raise Cancelada()
        _, raw = kit.req("GET", f"/api/v1/jobs/{jid}")
        st = json.loads(raw).get("Status")
        atualizar(b, etapa=f"{rotulo} — {int(time.time() - inicio)}s")
        if st == "ok":
            break
        if st == "working" and time.time() - ultima_checagem >= 60:
            ultima_checagem = time.time()
            atual = _baixar(jid)
            if atual and len(atual) == linhas_vistas:
                parado_desde = parado_desde or ultima_checagem
                if ultima_checagem - parado_desde >= 180:
                    return atual
            else:
                linhas_vistas, parado_desde = len(atual), None
        if st == "failed":
            raise RuntimeError("O Google recusou a busca (possível bloqueio temporário). Espere alguns minutos.")
        # o motor pode demorar a começar o job e a visitar os sites; dá folga antes de desistir
        if time.time() - inicio > corpo["max_time"] + 900:
            parcial = _baixar(jid)
            if parcial:
                with lock:
                    b["avisos"].append("O motor demorou demais; usei os resultados que ele já tinha.")
                return parcial
            raise RuntimeError("Tempo esgotado esperando o motor.")
        time.sleep(5)
    return _baixar(jid)

def executar(b):
    p = b["parametros"]
    t = TAMANHOS[p["tamanho"]]
    atualizar(b, estado="rodando", etapa="Localizando a cidade no mapa…", iniciado_em=time.time(), parcial=0)
    geo = localizar(p["cidade"], p["uf"], p.get("bairro"))
    if not geo:
        raise RuntimeError(f"Não encontrei \"{p['cidade']} - {p['uf']}\" no mapa.")
    lat, lon, bbox = geo
    onde = f"{p['bairro']}, {p['cidade']} - {p['uf']}" if p.get("bairro") else f"{p['cidade']} - {p['uf']}"
    corpo = {"name": f"painel:{b['id'][:8]}", "keywords": [f"{n} em {onde}" for n in p["nichos"]],
             "lang": "pt", "zoom": 15, "lat": str(lat), "lon": str(lon), "fast_mode": False,
             "radius": 3000 if p.get("bairro") else 10000,
             "depth": t["depth"], "email": True, "max_time": t["max_time"]}
    usa_grid = t["grid"] and bbox and not p.get("bairro")
    celulas = kit.grid_cells(bbox, t["grid"]) if usa_grid else [None]
    anterior = b["jobs_motor"][-1] if len(celulas) == 1 and b.get("jobs_motor") else None
    reuso = anterior if anterior and job_reaproveitavel(anterior) else None
    linhas = []
    for i, cel in enumerate(celulas, 1):
        rotulo = (f"Buscando no Google Maps — região {i}/{len(celulas)}" if len(celulas) > 1
                  else "Buscando no Google Maps")
        atualizar(b, progresso={"atual": i - 1, "total": len(celulas), "fase": "maps"})
        try:
            novas = rodar_job(b, dict(corpo, **cel) if cel else corpo, rotulo, jid=reuso)
        except Cancelada:
            raise
        except Exception as e:
            if len(celulas) == 1:
                raise
            with lock:
                b["avisos"].append(f"Região {i} pulada: {e}")
            continue
        linhas = kit.dedupe(linhas + novas)
        atualizar(b, parcial=len(linhas))
    if usa_grid:
        linhas = [r for r in linhas if kit.in_bbox(r, bbox)]
    novos = [lead_de(r) for r in linhas]

    com_site = [l for l in novos if l["site"]]
    feitos = 0
    atualizar(b, etapa=f"Visitando sites atrás de e-mail e WhatsApp — 0/{len(com_site)}",
              progresso={"atual": 0, "total": len(com_site), "fase": "sites"})
    with ThreadPoolExecutor(max_workers=8) as ex:
        for _ in ex.map(lambda l: enriquecer(l, p.get("redes", True)), com_site):
            feitos += 1
            if b.get("cancelar"):
                raise Cancelada()
            atualizar(b, etapa=f"Visitando sites atrás de e-mail e WhatsApp — {feitos}/{len(com_site)}",
                      progresso={"atual": feitos, "total": len(com_site), "fase": "sites"})
    ids = mesclar_leads(b, novos)
    ja_tinha = sum(1 for i in ids if len(leads[i]["buscas"]) > 1)
    atualizar(b, lead_ids=ids, novos=len(ids) - ja_tinha, estado="concluida", etapa="Concluída",
              concluido_em=time.time(), progresso=None)
    salvar_leads()

def trabalhador():
    while True:
        with fila_cond:
            while not fila:
                fila_cond.wait()
            bid = fila.pop(0)
            b = buscas.get(bid)
        if not b or b.get("cancelar"):
            continue
        try:
            executar(b)
        except Cancelada:
            atualizar(b, estado="cancelada", etapa="Cancelada", progresso=None)
        except urllib.error.HTTPError as e:
            atualizar(b, estado="erro", progresso=None,
                      etapa=f"O motor recusou a busca (HTTP {e.code}: {e.read().decode(errors='replace')[:200]})")
        except urllib.error.URLError as e:
            atualizar(b, estado="erro", progresso=None,
                      etapa=f"Motor fora do ar ({e.reason}). Abra o Docker e rode: docker compose up -d")
        except Exception as e:
            atualizar(b, estado="erro", etapa=str(e), progresso=None)
        salvar_busca(b)


# ── Visões para a API ──────────────────────────────────────────────────────────
def resumo_busca(b):
    ls = [leads[i] for i in b.get("lead_ids", []) if i in leads]
    out = {k: b.get(k) for k in ("id", "parametros", "estado", "etapa", "progresso", "criado_em",
                                 "iniciado_em", "concluido_em", "avisos", "parcial", "novos")}
    out.update(total=len(ls),
               com_whatsapp=sum(1 for l in ls if l["whatsapp"]),
               com_email=sum(1 for l in ls if l["email"]),
               sem_site=sum(1 for l in ls if not l["site"]),
               posicao_fila=(fila.index(b["id"]) + 1) if b["id"] in fila else 0)
    return out

def lead_publico(l):
    return {k: v for k, v in l.items() if k != "historico"} | {"n_hist": len(l.get("historico", [])),
                                                                "segmento": segmento_de(l) or segmento_de(l, so_ativos=False)}

def painel_inicio():
    with lock:
        ls = list(leads.values())
        por_status = {s: 0 for s in STATUS_LEAD}
        for l in ls:
            por_status[l["status"]] = por_status.get(l["status"], 0) + 1
        def top(campo, n=8):
            c = {}
            for l in ls:
                if l.get(campo):
                    c[l[campo]] = c.get(l[campo], 0) + 1
            return sorted(c.items(), key=lambda x: -x[1])[:n]
        eventos = []
        for l in ls:
            for e in l.get("historico", []):
                if e["tipo"] != "criado":
                    eventos.append(e | {"lead": l["id"], "nome": l["nome"]})
        eventos.sort(key=lambda e: -e["t"])
        semana = time.time() - 7 * 86400
        return {
            "total": len(ls),
            "com_whatsapp": sum(1 for l in ls if l["whatsapp"]),
            "com_email": sum(1 for l in ls if l["email"]),
            "sem_site": sum(1 for l in ls if not l["site"]),
            "por_status": por_status,
            "contatos_semana": sum(1 for e in eventos if e["t"] >= semana and e["tipo"] == "whatsapp"),
            "novos_semana": sum(1 for l in ls if l["criado_em"] >= semana),
            "cidades": top("cidade"), "bairros": top("bairro"), "categorias": top("categoria"),
            "eventos": eventos[:12],
            "buscas_ativas": sum(1 for b in buscas.values() if b["estado"] in ("rodando", "na_fila")),
        }

def registrar(l, tipo, txt):
    agora = time.time()
    l.setdefault("historico", []).append({"t": agora, "tipo": tipo, "txt": txt})
    l["atualizado_em"] = agora
    if tipo == "whatsapp":
        l["ultimo_contato"] = agora

def motor_ok():
    try:
        kit.req("GET", "/api/v1/jobs")
        return True
    except Exception:
        return False


# ── Segredos locais e login ────────────────────────────────────────────────────
def _segredo(nome):
    """Lê (ou cria) um segredo aleatório em painel/dados/<nome>. Compartilhado com os outros serviços."""
    caminho = os.path.join(DADOS, nome)
    try:
        with open(caminho, encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except OSError:
        pass
    v = secrets.token_hex(32)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(v)
    return v

API_TOKEN = _segredo("api_token")    # MCP e scripts locais (header X-Prospecta-Token)
WA_TOKEN = _segredo("wa_token")      # webhook do WAHA -> painel (header X-WA-Token)
WAHA_KEY = _segredo("waha_key")      # painel -> WAHA (header X-Api-Key)
WAHA_URL = os.environ.get("WAHA_URL", "http://127.0.0.1:3000")
WAHA_SESSAO = "default"
ARQ_AUTH = os.path.join(DADOS, "auth.json")
ARQ_SESSOES = os.path.join(DADOS, "sessoes.json")
sessoes = {}         # token do cookie -> expira_em

def _hash(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), 200_000).hex()

def auth_configurado():
    return bool(_le(ARQ_AUTH, {}).get("hash"))

def define_senha(senha):
    sal = secrets.token_hex(16)
    _grava(ARQ_AUTH, {"sal": sal, "hash": _hash(senha, sal)})

def confere_senha(senha):
    a = _le(ARQ_AUTH, {})
    return bool(a.get("hash")) and hmac.compare_digest(a["hash"], _hash(senha, a["sal"]))

def nova_sessao():
    tok = secrets.token_urlsafe(32)
    with lock:
        agora = time.time()
        for t in [t for t, exp in sessoes.items() if exp < agora]:
            del sessoes[t]
        sessoes[tok] = agora + 30 * 86400
        _grava(ARQ_SESSOES, sessoes)
    return tok


# ── WhatsApp interno (WAHA) ────────────────────────────────────────────────────
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

def chave_num(d):
    """Número -> chave de comparação: DDD + 8 últimos dígitos (ignora 55 e o 9º dígito)."""
    d = re.sub(r"\D", "", d or "")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11 and d[2] == "9":
        d = d[:2] + d[3:]
    return d if len(d) == 10 else ""

def lead_por_numero(numero):
    """Só números exatos que já estão no CRM (WhatsApp ou telefone do lead). Senão None."""
    k = chave_num(numero)
    if not k:
        return None
    with lock:
        for l in leads.values():
            if k in (chave_num(l.get("whatsapp")), chave_num(l.get("tel_digitos"))):
                return l
    return None

def salvar_conversas():
    with lock:
        _grava(ARQ_CONVERSAS, conversas)

def conversa_de(numero, lead):
    with lock:
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
    numero = re.sub(r"\D", "", numero or lead.get("whatsapp") or lead.get("tel_digitos") or "")
    if not lead_por_numero(numero):
        raise ValueError("Só envio para números de leads do CRM.")
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
    lead = lead_por_numero(numero)
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


# ── Agenda ─────────────────────────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone  # noqa: E402
BR = timezone(timedelta(hours=-3))  # Brasília (sem horário de verão desde 2019)
FMT = "%Y-%m-%d %H:%M"

def salvar_agenda():
    with lock:
        _grava(ARQ_AGENDA, agenda_dados)

def _hm(s):
    h, m = s.split(":")
    return int(h), int(m)

def slots_do_dia(dia):
    """Horários livres de uma data (date) segundo a disponibilidade, sem conflito e no futuro."""
    a = config["agenda"]
    if dia.weekday() not in a["dias"]:
        return []
    dur = max(10, int(a["duracao"]))
    ini = datetime(dia.year, dia.month, dia.day, *_hm(a["inicio"]), tzinfo=BR)
    fim = datetime(dia.year, dia.month, dia.day, *_hm(a["fim"]), tzinfo=BR)
    limite = datetime.now(BR) + timedelta(hours=float(a.get("antecedencia_h", 2)))
    ocupados = [(datetime.strptime(r["inicio"], FMT).replace(tzinfo=BR), int(r["duracao"]))
                for r in agenda_dados.get("reservas", []) if r.get("estado") != "cancelada"]
    out, t = [], ini
    while t + timedelta(minutes=dur) <= fim:
        livre = all(not (t < o + timedelta(minutes=d) and o < t + timedelta(minutes=dur)) for o, d in ocupados)
        if livre and t >= limite:
            out.append(t.strftime(FMT))
        t += timedelta(minutes=dur)
    return out

def proximos_slots(qtd=12, dias=10):
    hoje, out = datetime.now(BR).date(), []
    for i in range(dias):
        out += slots_do_dia(hoje + timedelta(days=i))
        if len(out) >= qtd:
            break
    return out[:qtd]

def reservar(lead, inicio, origem="manual"):
    with lock:
        try:
            dia = datetime.strptime(inicio, FMT).date()
        except ValueError:
            raise ValueError("Horário inválido.")
        if inicio not in slots_do_dia(dia):
            raise ValueError("Horário indisponível.")
        r = {"id": uuid.uuid4().hex[:12], "lead_id": lead["id"], "nome": lead["nome"], "inicio": inicio,
             "duracao": int(config["agenda"]["duracao"]), "origem": origem, "estado": "marcada", "criado_em": time.time()}
        agenda_dados.setdefault("reservas", []).append(r)
        lead["reuniao"] = inicio
        if lead["status"] != "reuniao":
            lead["status"] = "reuniao"
            registrar(lead, "status", "Status: Reunião marcada")
        registrar(lead, "agenda", f"Chamada marcada para {datetime.strptime(inicio, FMT).strftime('%d/%m às %H:%M')}"
                                  f"{' pela IA' if origem == 'ia' else ''}")
    salvar_agenda(); salvar_leads()
    return r

def fmt_slot(s):
    d = datetime.strptime(s, FMT)
    return f"{['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'][d.weekday()]} {d.strftime('%d/%m %H:%M')}"


# ── Agente de atendimento (IA via Claude Code da sua assinatura) ───────────────
pendentes_ia = {}    # numero -> horário em que a IA deve responder
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

SISTEMA_IA = """Você é um agente de pré-atendimento comercial por WhatsApp, em português do Brasil.
Regras:
- Use SOMENTE as informações da BASE DE CONHECIMENTO. Se não souber, diga que confirma na chamada.
- Mensagens curtas (1 a 3 frases), naturais, sem parecer robô, no máximo 1 emoji. Uma pergunta por vez.
- Objetivo: entender a necessidade e marcar uma chamada. Ofereça só horários da lista HORÁRIOS LIVRES
  (2 ou 3 opções). Quando o lead aceitar um horário da lista, use acao "agendar" com esse horário exato.
- Se pedirem algo que exige uma pessoa (negociação, reclamação, assunto fora da base), use acao "humano".
- Se a pessoa disser que não tem interesse ou pedir para parar, despeça-se educadamente e use acao "encerrar".
- Nunca invente preços, prazos ou promessas. Nunca diga que é humano se perguntarem.
Responda APENAS um objeto JSON, sem texto fora dele:
{"mensagem": "texto para enviar (vazio se não for responder)", "acao": "responder|agendar|humano|encerrar|nada",
 "horario": "AAAA-MM-DD HH:MM ou null", "resumo": "uma linha para o CRM"}"""

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


# ── Segmentos: situação digital da empresa -> estratégia e roteiro próprios ────
REDES = ("instagram.com", "facebook.com", "wa.me", "whatsapp.com", "linktr.ee")

def tem_site(l):
    s = (l.get("site") or "").lower()
    return bool(s) and not any(h in s for h in REDES)

def tem_instagram(l):
    return bool(l.get("instagram")) or "instagram.com" in (l.get("site") or "").lower()

def reputacao_baixa(l):
    return 0 < (l.get("nota") or 0) < 4.0 and (l.get("avaliacoes") or 0) >= 5

# ordem = prioridade: o lead cai no primeiro segmento LIGADO cuja regra bate
SEGMENTOS = {
    "reputacao": {"nome": "Nota baixa no Google", "regra": reputacao_baixa,
                  "descricao": "Nota abaixo de 4,0 com 5+ avaliações. Abordagem sobre atendimento e reputação, sem citar a nota."},
    "sem_presenca": {"nome": "Sem site e sem Instagram", "regra": lambda l: not tem_site(l) and not tem_instagram(l),
                     "descricao": "Só aparece no Google Maps. Quem procura não acha mais nada sobre a empresa."},
    "so_instagram": {"nome": "Só Instagram, sem site", "regra": lambda l: not tem_site(l) and tem_instagram(l),
                     "descricao": "Tem Instagram mas nenhum site: depende do algoritmo e perde quem pesquisa no Google."},
    "site_sem_instagram": {"nome": "Tem site, sem Instagram", "regra": lambda l: tem_site(l) and not tem_instagram(l),
                           "descricao": "Tem site, mas sem rede social ativa encontrada. Oportunidade de conteúdo e captação."},
    "site_e_instagram": {"nome": "Tem site e Instagram", "regra": lambda l: tem_site(l) and tem_instagram(l),
                         "descricao": "Presença completa. Foco em converter mais: automação, atendimento com IA, landing page."},
}

CAMPANHAS_PADRAO = {
    # Princípios de todos os roteiros: 1) gancho específico (algo real que vimos da empresa),
    # 2) a perda que ela tem hoje (cliente pesquisa e vai pro concorrente), 3) quem somos em 1 linha,
    # 4) pergunta de sim/não com pouco compromisso ("posso te mostrar?"), sem link, sem preço.
    "reputacao": {"ativo": False, "estrategia": (
        "Nunca cite a nota nem críticas: a empresa sabe e fica na defensiva. Fale de bastidores do atendimento: "
        "resposta rápida no WhatsApp, cliente que não fica sem retorno, pedido automático de avaliação para quem saiu "
        "satisfeito. Objeções: 'quanto custa' -> depende do volume, mostro na chamada de 15 min; 'já respondemos' -> "
        "pergunte quanto tempo leva no fim de semana. Objetivo: marcar a chamada."),
        "variantes": [
            "{saudacao}! Encontrei a {nome} pesquisando {categoria} em {cidade}. Trabalho ajudando empresas a responder todo cliente no WhatsApp na hora e a transformar quem saiu satisfeito em avaliação no Google. Posso te mostrar como funciona na prática?",
            "Olá, tudo bem? Vi a {nome} no Google. Uma coisa que mais pesa na escolha do cliente hoje é a rapidez da resposta e as avaliações recentes. Eu automatizo essas duas coisas. Faz sentido eu te mandar um exemplo?",
            "{saudacao}! Ajudo empresas de {cidade} a nunca deixar cliente sem resposta e a receber mais avaliações positivas, tudo pelo WhatsApp. Vi a {nome} e acho que encaixa bem. Você teria interesse em ver?",
        ]},
    "sem_presenca": {"ativo": True, "estrategia": (
        "A empresa só existe no Google Maps: quem pesquisa não acha site nem Instagram e fica com o concorrente que "
        "aparece melhor. Valorize o que ela já tem (avaliações, tempo de mercado) e mostre que está deixando cliente na "
        "mesa. Ofereça mostrar um exemplo ou um esboço da página dela, nunca o preço por mensagem. Objeções: 'já tenho "
        "muito cliente' -> site traz o cliente que paga melhor e pesquisa antes; 'não tenho tempo' -> nós fazemos tudo, "
        "ela só aprova; 'quanto custa' -> depende do que precisa, mostro na chamada de 15 min. Objetivo: marcar a chamada."),
        "variantes": [
            "{saudacao}! Vi a {nome} no Google{elogio}, mas não encontrei um site de vocês. Trabalho justamente ajudando empresas como a de vocês a aparecer melhor na internet e receber mais contatos pelo WhatsApp. Você teria interesse em ver como ficaria?",
            "Olá, tudo bem? Pesquisei {categoria} em {cidade} e a {nome} apareceu{elogio}. Só senti falta de um site: hoje o cliente pesquisa antes de chamar e, sem site, acaba indo para quem aparece mais completo. Posso te mostrar um exemplo do que eu faria para vocês?",
            "{saudacao}! Encontrei a {nome} no Google Maps{elogio}. Vocês já têm o mais difícil, que é a confiança dos clientes. O que falta é uma página que mostre isso para quem ainda não conhece vocês. Posso te mandar uma ideia de como ficaria?",
        ]},
    "so_instagram": {"ativo": True, "estrategia": (
        "Tem Instagram mas não tem site. Elogie o perfil de forma específica. Explique que o Instagram depende do "
        "algoritmo e só alcança quem já segue, enquanto quem pesquisa no Google nunca chega até o perfil. O site "
        "trabalha 24h, aparece no Google e leva direto ao WhatsApp. Objeções: 'o Instagram já basta' -> Instagram é para "
        "quem já conhece, o Google é para quem está procurando agora; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o Instagram da {nome}, trabalho muito bonito. Só não encontrei um site: quem pesquisa {categoria} em {cidade} no Google não chega até o perfil de vocês. Você teria interesse em ver como um site ligado ao Instagram e ao WhatsApp ficaria?",
            "Olá, tudo bem? Achei a {nome} pelo Google e fui parar no Instagram de vocês. O Instagram fala com quem já segue; o site pega quem está pesquisando agora e ainda não conhece. Posso te mostrar um exemplo?",
            "{saudacao}! O Instagram da {nome} está ótimo, mas ele depende do algoritmo. Eu ajudo empresas como a de vocês a ter um site que aparece no Google e leva o cliente direto para o WhatsApp de vocês. Faz sentido conversarmos 10 minutinhos?",
        ]},
    "site_sem_instagram": {"ativo": True, "estrategia": (
        "Tem site, mas não encontramos Instagram ativo. Não critique o site. Pergunte de onde vêm os clientes hoje e "
        "ofereça aumentar o retorno do que já existe: página de oferta para campanha, botão e atendimento automático "
        "no WhatsApp, conteúdo que gera procura. Objeções: 'já tenho site' -> a ideia é fazer o site trazer mais "
        "contato, não trocar; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o site da {nome}{elogio}, bem apresentado. Fiquei curioso: hoje a maioria dos clientes chega pelo Google ou por indicação? Ajudo empresas de {cidade} a fazer o site gerar mais conversas no WhatsApp.",
            "Olá, tudo bem? Encontrei a {nome} e o site de vocês pesquisando {categoria} em {cidade}. Trabalho com páginas e automações que fazem quem visita o site virar contato no WhatsApp. Você teria interesse em ver um exemplo?",
            "{saudacao}! O site da {nome} já faz a parte dele, mas notei que vocês não estão no Instagram, onde muita gente de {cidade} descobre empresas do seu ramo. Posso te mostrar como juntar os dois para trazer mais clientes?",
        ]},
    "site_e_instagram": {"ativo": True, "estrategia": (
        "Presença digital completa: NÃO venda site. Fale de conversão e velocidade: atendimento com IA no WhatsApp que "
        "responde em segundos, inclusive à noite e no fim de semana, qualifica e já marca horário; landing page para "
        "campanhas. Pergunte sobre volume de mensagens e quanto tempo levam para responder. Objeções: 'já temos "
        "atendente' -> a IA cobre fora do horário e o pico, o atendente fecha; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o site e o Instagram da {nome}{elogio}, tudo muito bem feito. Pergunta rápida: quando alguém chama no WhatsApp à noite ou no fim de semana, vocês conseguem responder na hora? Eu automatizo esse atendimento com IA.",
            "Olá, tudo bem? Acompanhei a {nome} pelo Google e pelo Instagram. Trabalho com um atendente de IA no WhatsApp que responde em segundos, tira dúvidas e já agenda com o cliente. Você teria interesse em ver funcionando?",
            "{saudacao}! A {nome} já tem uma presença online forte. O próximo passo costuma ser não perder ninguém no WhatsApp: resposta imediata, 24h, com agendamento automático. Posso te mostrar como ficaria para vocês?",
        ]},
}

FOLLOWUP_PADRAO = {"ativo": True, "dias": [2, 5], "variantes": [
    # 1º: retomada leve, oferece algo concreto
    ["{saudacao}! Passando só para saber se você viu minha mensagem sobre a {nome} 🙂 Se quiser, monto um exemplo rápido para você ver sem compromisso.",
     "Oi! Retomando por aqui: ainda faz sentido eu te mostrar a ideia para a {nome}? É coisa de 10 minutinhos.",
     "{saudacao}! Sei que a rotina é corrida. Posso te mandar o exemplo por aqui mesmo, aí você vê quando tiver um tempinho?"],
    # 2º: despedida (quebra o padrão e costuma gerar resposta)
    ["Última mensagem, prometo! Se não for o momento, sem problema. Quando fizer sentido, é só responder aqui. Sucesso para a {nome}!",
     "Vou parar de insistir 🙂 Fica o contato salvo: quando quiser melhorar a presença da {nome} na internet, é só me chamar.",
     "Imagino que agora não seja prioridade, tudo certo. Se mudar, é só responder esta mensagem. Um abraço!"],
]}

def segmento_de(l, so_ativos=True):
    for sid, s in SEGMENTOS.items():
        if so_ativos and not config["campanhas"].get(sid, {}).get("ativo"):
            continue
        try:
            if s["regra"](l):
                return sid
        except Exception:
            continue
    return None

def saudacao():
    h = datetime.now(BR).hour
    return "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"

def nome_curto(nome):
    """'Litoral Tec Ar - Vendas, Instalação e Manutenção' -> 'Litoral Tec Ar'; nomes em CAIXA ALTA viram Título."""
    n = re.split(r"\s+[-|–—:]\s+|\s*\|\s*", nome or "")[0].strip() or (nome or "")
    if n.isupper() and len(n) > 4:
        # 1ª palavra curta costuma ser sigla da marca (RD, IMS, M.E.R): mantém
        n = " ".join(p if i == 0 and len(p) <= 5 else p.capitalize() for i, p in enumerate(n.split()))
        n = re.sub(r"(?<= )(De|Da|Do|Das|Dos|E)(?= )", lambda m: m.group(0).lower(), n)
    return n

def preenche(texto, l):
    nota, aval = l.get("nota") or 0, l.get("avaliacoes") or 0
    # {elogio}: só elogia o que é verdade; vazio para nota mediana (o texto continua natural sem ele)
    elogio = (" com ótimas avaliações" if nota >= 4.6 and aval >= 15 else
              " com boas avaliações" if nota >= 4.2 and aval >= 5 else "")
    cidade = l.get("cidade") or "sua cidade"
    out = (texto.replace("{nome}", nome_curto(l.get("nome"))).replace("{cidade}", cidade).replace("{bairro}", l.get("bairro") or cidade)
           .replace("{categoria}", (l.get("categoria") or "empresas").lower()).replace("{nota}", str(nota).replace(".", ","))
           .replace("{avaliacoes}", str(aval)).replace("{elogio}", elogio).replace("{saudacao}", saudacao()))
    return re.sub(r"[ \t]+", " ", out).strip()

_ultima_variante = {}

def escolhe_variante(chave, variantes):
    """Rodízio: nunca repete a mesma variação seguida (textos idênticos em massa chamam atenção do WhatsApp)."""
    i = _ultima_variante.get(chave, -1)
    opcoes = [j for j in range(len(variantes)) if j != i] or [0]
    j = random.choice(opcoes)
    _ultima_variante[chave] = j
    return variantes[j]


# ── Disparo automático (primeira mensagem) com limites para não ser bloqueado ──
ARQ_ENVIOS = os.path.join(DADOS, "envios.json")
envios = _le(ARQ_ENVIOS, {"dia": "", "n": 0, "proximo": 0, "ultimo_erro": ""})

def elegiveis(segmento=None):
    """Leads novos com WhatsApp que caem num segmento LIGADO (ou no segmento pedido)."""
    ae = config["auto_envio"]
    filtro = set(ae.get("buscas") or [])
    with lock:
        com_conversa = {c["lead_id"] for c in conversas.values()}
        ls = [l for l in leads.values() if l["status"] == "novo" and l.get("whatsapp") and not l.get("optout")
              and not l.get("sem_whatsapp") and not l.get("fechado") and l["id"] not in com_conversa
              and (not filtro or filtro & set(l.get("buscas") or []))
              and (segmento_de(l) == segmento if segmento else segmento_de(l))]
    # mais promissores primeiro: nota ponderada pelo nº de avaliações
    import math
    return sorted(ls, key=lambda l: -(l.get("nota") or 0) * math.log10((l.get("avaliacoes") or 0) + 1))

def proximo_followup():
    """(conversa, lead, índice) do follow-up vencido mais antigo; só para quem nunca respondeu."""
    fu = config["followup"]
    if not fu.get("ativo"):
        return None
    dias, agora, melhor = fu.get("dias") or [], time.time(), None
    with lock:
        for c in conversas.values():
            l = leads.get(c["lead_id"])
            k = c.get("followups", 0)
            if not l or k >= len(dias) or k >= len(fu["variantes"]) or not fu["variantes"][k]:
                continue
            if l.get("optout") or l["status"] != "contatado" or not c["msgs"]:
                continue
            if any(m["de"] == "lead" for m in c["msgs"]) or c["msgs"][0]["de"] == "lead":
                continue
            vence = c["msgs"][0]["t"] + float(dias[k]) * 86400
            if vence <= agora and (not melhor or vence < melhor[0]):
                melhor = (vence, c, l, k)
    return melhor[1:] if melhor else None

def na_janela(ae):
    agora = datetime.now(BR)
    return agora.weekday() in ae["dias"] and ae["hora_ini"] <= agora.strftime("%H:%M") < ae["hora_fim"]

def disparador():
    while True:
        time.sleep(20)
        try:
            ae = config["auto_envio"]
            hoje = datetime.now(BR).strftime("%Y-%m-%d")
            if envios["dia"] != hoje:
                envios.update(dia=hoje, n=0)
            if not ae.get("ativo") or not na_janela(ae) or envios["n"] >= int(ae["limite_dia"]) or time.time() < envios["proximo"]:
                continue
            if wa_status()["conexao"] != "conectado":
                continue
            # follow-up de quem não respondeu tem prioridade sobre contato novo
            fu = proximo_followup()
            if fu:
                c, l, k = fu
                try:
                    wa_enviar(l, preenche(escolhe_variante(f"fu{k}", config["followup"]["variantes"][k]), l),
                              de="followup", numero=c["numero"])
                    with lock:
                        c["followups"] = k + 1
                        registrar(l, "nota", f"Follow-up {k + 1} enviado automaticamente")
                    salvar_conversas(); salvar_leads()
                    envios["n"] += 1
                    envios["ultimo_erro"] = ""
                except ValueError as e:
                    with lock:
                        c["followups"] = 99
                        registrar(l, "nota", f"Follow-up cancelado: {e}")
                    salvar_conversas()
                    continue
                envios["proximo"] = time.time() + random.uniform(int(ae["intervalo_min"]), int(ae["intervalo_max"]))
                _grava(ARQ_ENVIOS, envios)
                continue
            fila_l = elegiveis()
            if not fila_l:
                continue
            l = fila_l[0]
            try:
                wa_enviar(l, primeira_mensagem(l), de="auto")
                with lock:
                    l["segmento_envio"] = segmento_de(l) or segmento_de(l, so_ativos=False)
                envios["n"] += 1
                envios["ultimo_erro"] = ""
            except ValueError as e:  # sem WhatsApp etc.: pula para o próximo sem gastar o intervalo
                with lock:
                    l["sem_whatsapp"] = True
                    registrar(l, "nota", f"Disparo automático pulou: {e}")
                salvar_leads()
                continue
            envios["proximo"] = time.time() + random.uniform(int(ae["intervalo_min"]), int(ae["intervalo_max"]))
        except Exception as e:
            envios["ultimo_erro"] = str(e)[:200]
            envios["proximo"] = time.time() + 300
        _grava(ARQ_ENVIOS, envios)

def respondedor():
    while True:
        time.sleep(3)
        agora = time.time()
        with lock:
            prontos = [n for n, t in pendentes_ia.items() if t <= agora]
            for n in prontos:
                del pendentes_ia[n]
        for n in prontos:
            try:
                ia_responder(n)
            except Exception as e:
                with lock:
                    c = conversas.get(n)
                    if c:
                        c["ia_erro"] = str(e)[:300]
                salvar_conversas()

def resumo_conversa(c):
    l = leads.get(c["lead_id"]) or {}
    u = c["msgs"][-1] if c["msgs"] else {}
    return {"numero": c["numero"], "lead_id": c["lead_id"], "nome": l.get("nome"), "status": l.get("status"),
            "ia": c.get("ia"), "ia_motivo": c.get("ia_motivo"), "ia_erro": c.get("ia_erro"), "nao_lidas": c.get("nao_lidas", 0),
            "ultima": u.get("txt", "")[:140], "ultima_de": u.get("de"), "ultima_em": c.get("ultima_em"),
            "aguardando_ia": c["numero"] in pendentes_ia}


# ── HTTP ───────────────────────────────────────────────────────────────────────
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
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
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
        return path in ("/", "/index.html", "/favicon.ico") or path.startswith("/api/auth/") or (metodo == "POST" and path == "/api/wa/evento")

    def _guarda(self, metodo):
        path = self._rota()
        if self._publico(metodo, path) or self._autorizado():
            return False
        self._envia(401, {"erro": "Faça login.", "login": True})
        return True

    def _auth(self, metodo, path):
        if path == "/api/auth/estado" and metodo == "GET":
            return self._envia(200, {"configurado": auth_configurado(), "logado": self._autorizado()})
        if metodo != "POST":
            return self._envia(404, {"erro": "não encontrado"})
        d = self._corpo()
        senha = str(d.get("senha") or "")
        if path == "/api/auth/criar":
            if auth_configurado():
                return self._envia(409, {"erro": "A senha já foi criada."})
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                return self._envia(403, {"erro": "Crie a senha no próprio computador."})
            if len(senha) < 6:
                return self._envia(400, {"erro": "Use pelo menos 6 caracteres."})
            define_senha(senha)
        elif path == "/api/auth/entrar":
            if not confere_senha(senha):
                time.sleep(1.5)
                return self._envia(401, {"erro": "Senha incorreta."})
        elif path == "/api/auth/sair":
            with lock:
                sessoes.pop(self._cookie(), None)
                _grava(ARQ_SESSOES, sessoes)
            self._extra = [("Set-Cookie", "prospecta=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")]
            return self._envia(200, {"ok": True})
        else:
            return self._envia(404, {"erro": "não encontrado"})
        self._extra = [("Set-Cookie", f"prospecta={nova_sessao()}; Path=/; Max-Age={30 * 86400}; HttpOnly; SameSite=Strict")]
        return self._envia(200, {"ok": True})

    # ── atendimento: WhatsApp, conversas, agente, agenda ──
    def _atendimento(self, metodo, path):
        """Devolve True se tratou a rota."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if path == "/api/wa/evento" and metodo == "POST":
            if not hmac.compare_digest(self.headers.get("X-WA-Token") or "", WA_TOKEN):
                self._envia(401, {"erro": "token inválido"}); return True
            ev = self._corpo()
            threading.Thread(target=wa_evento, args=(ev,), daemon=True).start()
            self._envia(200, {"ok": True}); return True
        if path == "/api/wa/status" and metodo == "GET":
            self._envia(200, wa_status()); return True
        if path == "/api/wa/conectar" and metodo == "POST":
            waha_garante_sessao(); self._envia(200, wa_status()); return True
        if path == "/api/wa/sair" and metodo == "POST":
            try:
                waha("POST", f"/api/sessions/{WAHA_SESSAO}/logout")
            except urllib.error.HTTPError:
                pass
            self._envia(200, {"ok": True}); return True
        if path == "/api/wa/enviar" and metodo == "POST":
            d = self._corpo()
            l = leads.get(d.get("lead_id") or "") or lead_por_numero(d.get("numero") or "")
            if not l:
                self._envia(400, {"erro": "Só envio para leads do CRM."}); return True
            if l.get("optout"):
                self._envia(400, {"erro": "Esse lead pediu para não receber mensagens."}); return True
            try:
                c = wa_enviar(l, d.get("texto"), numero=d.get("numero") or None)
            except ValueError as e:
                self._envia(400, {"erro": str(e)}); return True
            self._envia(200, {"conversa": c, "lead": l}); return True
        if path == "/api/conversas" and metodo == "GET":
            with lock:
                lista = sorted((resumo_conversa(c) for c in conversas.values()), key=lambda x: -(x["ultima_em"] or 0))
            self._envia(200, lista); return True
        m = re.fullmatch(r"/api/conversas/(\d+)(?:/(ia|lida))?", path)
        if m and m.group(1) in conversas:
            c = conversas[m.group(1)]
            if metodo == "GET" and not m.group(2):
                with lock:
                    self._envia(200, resumo_conversa(c) | {"msgs": c["msgs"][-200:], "lead": leads.get(c["lead_id"])})
                return True
            if metodo == "POST" and m.group(2) == "lida":
                with lock:
                    c["nao_lidas"] = 0
                salvar_conversas(); self._envia(200, {"ok": True}); return True
            if metodo == "POST" and m.group(2) == "ia":
                d = self._corpo()
                with lock:
                    c["ia"] = bool(d.get("ativa"))
                    c["ia_motivo"] = None if c["ia"] else "Desligada por você"
                    c.pop("ia_erro", None)
                    if c["ia"] and c["msgs"] and c["msgs"][-1]["de"] == "lead" and config["agente"].get("auto_responder"):
                        pendentes_ia[c["numero"]] = time.time() + 3
                salvar_conversas(); self._envia(200, resumo_conversa(c)); return True
        if path == "/api/agente" and metodo == "GET":
            self._envia(200, {"agente": config["agente"], "auto_envio": config["auto_envio"], "envios": envios,
                              "elegiveis": len(elegiveis()), "claude": bool(claude_bin()), "chave_api": bool(chave_api()),
                              "janela": na_janela(config["auto_envio"])})
            return True
        if path == "/api/agente" and metodo == "PUT":
            d = self._corpo()
            if "chave_api" in d:  # vazio remove; nunca volta para o navegador
                k = str(d.get("chave_api") or "").strip()
                if k:
                    with open(ARQ_CHAVE, "w", encoding="utf-8") as f:
                        f.write(k)
                elif os.path.exists(ARQ_CHAVE):
                    os.remove(ARQ_CHAVE)
            with lock:
                if isinstance(d.get("agente"), dict):
                    a = d["agente"]
                    config["agente"].update(base=str(a.get("base", config["agente"]["base"]))[:12000],
                                            instrucoes=str(a.get("instrucoes", config["agente"]["instrucoes"]))[:4000],
                                            auto_responder=bool(a.get("auto_responder", config["agente"]["auto_responder"])),
                                            modelo=a.get("modelo") if a.get("modelo") in ("haiku", "sonnet", "opus") else config["agente"]["modelo"],
                                            espera_s=max(5, min(300, int(a.get("espera_s", config["agente"]["espera_s"])))))
                if isinstance(d.get("auto_envio"), dict):
                    e, ae = d["auto_envio"], config["auto_envio"]
                    ae.update(ativo=bool(e.get("ativo", ae["ativo"])),
                              modo=e.get("modo") if e.get("modo") in ("template", "ia") else ae["modo"],
                              template=str(e.get("template", ae["template"])),
                              limite_dia=max(1, min(200, int(e.get("limite_dia", ae["limite_dia"])))),
                              intervalo_min=max(30, int(e.get("intervalo_min", ae["intervalo_min"]))),
                              intervalo_max=max(30, int(e.get("intervalo_max", ae["intervalo_max"]))),
                              hora_ini=str(e.get("hora_ini", ae["hora_ini"]))[:5], hora_fim=str(e.get("hora_fim", ae["hora_fim"]))[:5],
                              dias=[int(x) for x in e.get("dias", ae["dias"]) if 0 <= int(x) <= 6],
                              buscas=[str(x) for x in e.get("buscas", ae["buscas"])])
                    ae["intervalo_max"] = max(ae["intervalo_max"], ae["intervalo_min"])
            salvar_config(); self._envia(200, {"agente": config["agente"], "auto_envio": config["auto_envio"]}); return True
        if path == "/api/agente/primeira" and metodo == "POST":
            d = self._corpo()
            l = leads.get(d.get("lead_id") or "")
            if not l:
                self._envia(404, {"erro": "Lead não encontrado."}); return True
            try:
                self._envia(200, {"texto": primeira_mensagem(l, d.get("modo"))})
            except Exception as e:
                self._envia(500, {"erro": str(e)})
            return True
        if path == "/api/agente/simular" and metodo == "POST":
            # testa a IA sem enviar nada: conversa fictícia com um lead real
            d = self._corpo()
            l = leads.get(d.get("lead_id") or "") or next(iter(leads.values()), None)
            if not l:
                self._envia(400, {"erro": "Sem leads para simular."}); return True
            c = {"msgs": [{"t": time.time(), "de": m.get("de", "lead"), "txt": str(m.get("txt", ""))} for m in d.get("msgs", [])][-30:]}
            try:
                self._envia(200, ia_decide(l, c))
            except Exception as e:
                self._envia(500, {"erro": str(e)})
            return True
        if path == "/api/campanhas" and metodo == "GET":
            with lock:
                todos = [l for l in leads.values() if l.get("whatsapp")]
                cont = {sid: {"total": sum(1 for l in todos if SEGMENTOS[sid]["regra"](l)),
                              "na_fila": len(elegiveis(sid)) if config["campanhas"][sid].get("ativo") else 0} for sid in SEGMENTOS}
                fila_fu = sum(1 for c in conversas.values() if c.get("followups", 0) < len(config["followup"].get("dias") or [])
                              and not any(m["de"] == "lead" for m in c["msgs"])
                              and (leads.get(c["lead_id"]) or {}).get("status") == "contatado")
            self._envia(200, {"segmentos": [{"id": sid, "nome": s["nome"], "descricao": s["descricao"], **cont[sid],
                                             **config["campanhas"][sid]} for sid, s in SEGMENTOS.items()],
                              "followup": config["followup"], "followup_pendentes": fila_fu})
            return True
        if path == "/api/campanhas" and metodo == "PUT":
            d = self._corpo()
            with lock:
                for sid, c in (d.get("campanhas") or {}).items():
                    if sid not in SEGMENTOS or not isinstance(c, dict):
                        continue
                    alvo = config["campanhas"][sid]
                    if "ativo" in c: alvo["ativo"] = bool(c["ativo"])
                    if "estrategia" in c: alvo["estrategia"] = str(c["estrategia"])[:2000]
                    if "variantes" in c: alvo["variantes"] = [str(v)[:1500] for v in c["variantes"] if str(v).strip()][:10]
                f = d.get("followup")
                if isinstance(f, dict):
                    fu = config["followup"]
                    if "ativo" in f: fu["ativo"] = bool(f["ativo"])
                    if "dias" in f: fu["dias"] = [max(1, min(60, float(x))) for x in f["dias"]][:4]
                    if "variantes" in f: fu["variantes"] = [[str(v)[:1500] for v in grupo if str(v).strip()][:6] for grupo in f["variantes"]][:4]
            salvar_config(); self._envia(200, {"ok": True}); return True
        if path == "/api/campanhas/previa" and metodo == "POST":
            d = self._corpo()
            sid = d.get("segmento")
            with lock:
                exemplos = [l for l in leads.values() if segmento_de(l, so_ativos=False) == sid] or list(leads.values())
            if not exemplos:
                self._envia(400, {"erro": "Sem leads para a prévia."}); return True
            l = leads.get(d.get("lead_id") or "") or random.choice(exemplos)
            self._envia(200, {"texto": preenche(str(d.get("texto") or ""), l), "lead": l.get("nome")}); return True
        if path == "/api/agenda" and metodo == "GET":
            try:
                dia = datetime.strptime((q.get("dia") or [""])[0], "%Y-%m-%d").date()
            except ValueError:
                dia = datetime.now(BR).date()
            with lock:
                rs = sorted((r for r in agenda_dados.get("reservas", []) if r.get("estado") != "cancelada"), key=lambda r: r["inicio"])
                self._envia(200, {"config": config["agenda"], "dia": dia.isoformat(), "slots": slots_do_dia(dia), "reservas": rs})
            return True
        if path == "/api/agenda/config" and metodo == "PUT":
            d = self._corpo()
            with lock:
                a = config["agenda"]
                if re.fullmatch(r"\d\d:\d\d", str(d.get("inicio", ""))): a["inicio"] = d["inicio"]
                if re.fullmatch(r"\d\d:\d\d", str(d.get("fim", ""))): a["fim"] = d["fim"]
                if "dias" in d: a["dias"] = sorted({int(x) for x in d["dias"] if 0 <= int(x) <= 6})
                if "duracao" in d: a["duracao"] = max(10, min(240, int(d["duracao"])))
                if "antecedencia_h" in d: a["antecedencia_h"] = max(0, min(72, float(d["antecedencia_h"])))
            salvar_config(); self._envia(200, config["agenda"]); return True
        if path == "/api/agenda/reservar" and metodo == "POST":
            d = self._corpo()
            l = leads.get(d.get("lead_id") or "")
            if not l:
                self._envia(404, {"erro": "Lead não encontrado."}); return True
            try:
                self._envia(200, reservar(l, str(d.get("inicio") or ""), "manual"))
            except ValueError as e:
                self._envia(409, {"erro": str(e)})
            return True
        m = re.fullmatch(r"/api/agenda/(\w+)/cancelar", path)
        if m and metodo == "POST":
            with lock:
                r = next((r for r in agenda_dados.get("reservas", []) if r["id"] == m.group(1)), None)
                if r:
                    r["estado"] = "cancelada"
                    l = leads.get(r["lead_id"])
                    if l:
                        registrar(l, "agenda", f"Chamada de {datetime.strptime(r['inicio'], FMT).strftime('%d/%m %H:%M')} cancelada")
                        l.pop("reuniao", None)
            salvar_agenda(); salvar_leads()
            self._envia(200 if r else 404, r or {"erro": "não encontrado"}); return True
        return False

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
        if path == "/api/status":
            return self._envia(200, {"motor": motor_ok(), "fila": len(fila)})
        if path == "/api/municipios":
            return self._envia(200, [{k: m[k] for k in ("n", "uf", "ddd", "cap")} for m in municipios()])
        if path == "/api/inicio":
            return self._envia(200, painel_inicio())
        if path == "/api/config":
            return self._envia(200, config)
        if path == "/api/buscas":
            with lock:
                lista = sorted((resumo_busca(b) for b in buscas.values()), key=lambda x: -x["criado_em"])
            return self._envia(200, lista)
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
        m = re.fullmatch(r"/api/buscas/([\w-]+)", self._rota())
        if not m or m.group(1) not in buscas:
            return self._envia(404, {"erro": "não encontrado"})
        manter_trabalhados = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("leads") != ["apagar"]
        with lock:
            b = buscas.pop(m.group(1))
            b["cancelar"] = True
            if b["id"] in fila:
                fila.remove(b["id"])
            for lid in b.get("lead_ids", []):
                l = leads.get(lid)
                if not l:
                    continue
                if b["id"] in l["buscas"]:
                    l["buscas"].remove(b["id"])
                trabalhado = l["status"] != "novo" or l.get("obs") or len(l.get("historico", [])) > 1
                if not l["buscas"] and not (manter_trabalhados and trabalhado):
                    del leads[lid]
        try:
            os.remove(os.path.join(DIR_BUSCAS, f"{b['id']}.json"))
        except OSError:
            pass
        salvar_leads()
        for jid in b.get("jobs_motor", []):
            try:
                kit.req("DELETE", f"/api/v1/jobs/{jid}")
            except Exception:
                pass
        self._envia(200, {"ok": True})


def main():
    carregar()
    sessoes.update(_le(ARQ_SESSOES, {}))
    threading.Thread(target=trabalhador, daemon=True).start()
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
