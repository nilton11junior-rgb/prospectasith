"""Fila de buscas no motor do Google Maps e enriquecimento pelo site da empresa (e-mail, WhatsApp, redes)."""
import csv, io, json, re, time
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from estado import TAMANHOS, buscas, fila, fila_cond, leads, lock, salvar_busca, salvar_leads
from normaliza import lead_de, localizar, mesclar_leads, whatsapp_em
from estado import kit


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
