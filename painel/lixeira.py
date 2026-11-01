"""Lixeira de buscas: descartar uma busca ruim sem perder o que já foi trabalhado, com restauração.

Mandar para a lixeira tira da base os leads que vieram SÓ dessa busca e nunca foram trabalhados
(guardados dentro da própria busca, para restaurar). Lead trabalhado, ou que também veio de outra
busca, continua na base. Só a exclusão definitiva apaga de verdade, e só depois da lixeira.
"""
import os, time
from estado import DIR_BUSCAS, buscas, fila, kit, leads, lock, salvar_busca, salvar_leads
from visoes import resumo_busca

DIAS_NA_LIXEIRA = 30


def _trabalhado(l):
    return l["status"] != "novo" or bool(l.get("obs")) or len(l.get("historico", [])) > 1


def ativas():
    """Buscas fora da lixeira (as que a tela Buscas mostra), da mais recente para a mais antiga."""
    with lock:
        return sorted((resumo_busca(b) for b in buscas.values() if not b.get("lixeira_em")), key=lambda x: -x["criado_em"])


def lista():
    """Buscas na lixeira, a que entrou por último primeiro."""
    limpar_vencidas()
    with lock:
        out = []
        for b in buscas.values():
            if b.get("lixeira_em"):
                r = resumo_busca(b) | {"lixeira_em": b["lixeira_em"], "lixeira_motivo": b.get("lixeira_motivo", ""),
                                       "leads_guardados": len(b.get("lixeira_leads") or {}),
                                       "dias_restantes": max(0, DIAS_NA_LIXEIRA - int((time.time() - b["lixeira_em"]) // 86400))}
                r["total"] += r["leads_guardados"]  # o resumo só conta quem ainda está na base
                out.append(r)
        return sorted(out, key=lambda x: -x["lixeira_em"])


def mandar(bid, motivo=""):
    with lock:
        b = buscas.get(bid)
        if not b:
            raise KeyError(bid)
        if b["estado"] in ("rodando", "na_fila"):
            raise ValueError("Cancele a busca antes de mandar para a lixeira.")
        if b.get("lixeira_em"):
            raise ValueError("Essa busca já está na lixeira.")
        guardados = {}
        for lid in b.get("lead_ids", []):
            l = leads.get(lid)
            if l and l["buscas"] == [bid] and not _trabalhado(l):
                guardados[lid] = leads.pop(lid)
        b["lixeira_em"], b["lixeira_motivo"], b["lixeira_leads"] = time.time(), str(motivo or "")[:80], guardados
    salvar_busca(b)
    salvar_leads()
    return b


def restaurar(bid):
    with lock:
        b = buscas.get(bid)
        if not b or not b.get("lixeira_em"):
            raise KeyError(bid)
        for lid, l in (b.pop("lixeira_leads", None) or {}).items():
            leads.setdefault(lid, l)
        b.pop("lixeira_em", None)
        b.pop("lixeira_motivo", None)
    salvar_busca(b)
    salvar_leads()
    return b


def excluir(bid, manter_trabalhados=True):
    """Exclusão definitiva. Só vale para busca que está na lixeira."""
    with lock:
        b = buscas.get(bid)
        if not b:
            raise KeyError(bid)
        if not b.get("lixeira_em"):
            raise ValueError("Mande a busca para a lixeira antes de excluir de vez.")
        buscas.pop(bid)
        b["cancelar"] = True
        if bid in fila:
            fila.remove(bid)
        for lid in b.get("lead_ids", []):
            l = leads.get(lid)
            if not l:
                continue
            if bid in l["buscas"]:
                l["buscas"].remove(bid)
            if not l["buscas"] and not (manter_trabalhados and _trabalhado(l)):
                del leads[lid]
    try:
        os.remove(os.path.join(DIR_BUSCAS, f"{bid}.json"))
    except OSError:
        pass
    salvar_leads()
    for jid in b.get("jobs_motor", []):  # libera o resultado guardado no motor
        try:
            kit.req("DELETE", f"/api/v1/jobs/{jid}")
        except Exception:
            pass
    return b


def limpar_vencidas(dias=DIAS_NA_LIXEIRA):
    """Apaga de vez o que está na lixeira há mais de `dias` dias. Devolve quantas apagou."""
    limite = time.time() - dias * 86400
    with lock:
        vencidas = [bid for bid, b in buscas.items() if b.get("lixeira_em") and b["lixeira_em"] < limite]
    for bid in vencidas:
        excluir(bid)
    return len(vencidas)


def esvaziar():
    with lock:
        todas = [bid for bid, b in buscas.items() if b.get("lixeira_em")]
    for bid in todas:
        excluir(bid)
    return len(todas)
