"""Disparo automático da primeira mensagem e follow-ups, com limites para não ser bloqueado."""
import random, time
from datetime import datetime
from estado import ARQ_ENVIOS, _grava, config, conversas, envios, leads, lock, pendentes_ia, registrar, salvar_leads
from campanhas import escolhe_variante, preenche, segmento_de
from agenda import BR
from whatsapp import salvar_conversas, wa_enviar, wa_status
from agente import ia_responder, primeira_mensagem


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
