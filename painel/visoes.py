"""Resumos que a API devolve para a tela (busca, lead, início, conversa)."""
import time
from estado import STATUS_LEAD, buscas, fila, leads, lock, pendentes_ia
from campanhas import segmento_de
from estado import kit


def resumo_busca(b):
    ls = [leads[i] for i in b.get("lead_ids", []) if i in leads]
    out = {k: b.get(k) for k in ("id", "parametros", "estado", "etapa", "progresso", "criado_em",
                                 "iniciado_em", "concluido_em", "avisos", "parcial", "novos", "origem", "scraper_job_id")}
    out.update(total=len(ls),
               com_whatsapp=sum(1 for l in ls if l["whatsapp"]),
               com_email=sum(1 for l in ls if l["email"]),
               sem_site=sum(1 for l in ls if not l["site"]),
               posicao_fila=(fila.index(b["id"]) + 1) if b["id"] in fila else 0)
    return out


def lead_publico(l):
    return {k: v for k, v in l.items() if k not in ("historico", "auditoria")} | {"n_hist": len(l.get("historico", [])),
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


def motor_ok():
    try:
        kit.req("GET", "/api/v1/jobs")
        return True
    except Exception:
        return False


def resumo_conversa(c):
    l = leads.get(c["lead_id"]) or {}
    u = c["msgs"][-1] if c["msgs"] else {}
    return {"numero": c["numero"], "lead_id": c["lead_id"], "nome": l.get("nome"), "status": l.get("status"),
            "ia": c.get("ia"), "ia_motivo": c.get("ia_motivo"), "ia_erro": c.get("ia_erro"), "nao_lidas": c.get("nao_lidas", 0),
            "ultima": u.get("txt", "")[:140], "ultima_de": u.get("de"), "ultima_em": c.get("ultima_em"),
            "aguardando_ia": c["numero"] in pendentes_ia}
