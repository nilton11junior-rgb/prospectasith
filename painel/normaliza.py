"""Geografia (IBGE/OpenStreetMap) e normalização brasileira: telefone, WhatsApp e lead a partir do Google."""
import hashlib, json, os, re, time, unicodedata
import urllib.error, urllib.parse, urllib.request
from estado import CAMPOS_CONTATO, HERE, UA, leads, lock


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
