"""Rotas HTTP de atendimento: WhatsApp, conversas, agente IA, campanhas e agenda.

O handler (server.H) chama atender() antes das rotas de buscas e leads; devolve True se tratou o pedido.
"""
import hmac, os, random, re, threading, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime
from estado import WAHA_SESSAO, WA_TOKEN, agenda_dados, config, conversas, envios, leads, lock, pendentes_ia, registrar, salvar_config, salvar_leads
from campanhas import SEGMENTOS, preenche, segmento_de
from visoes import resumo_conversa
from agenda import BR, FMT, reservar, salvar_agenda, slots_do_dia
from whatsapp import lead_por_numero, salvar_conversas, wa_enviar, wa_evento, wa_status, waha, waha_garante_sessao
from agente import ARQ_CHAVE, chave_api, claude_bin, ia_decide, primeira_mensagem
from disparo import elegiveis, na_janela


def atender(h, metodo, path):
    """Devolve True se tratou a rota."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query)
    if path == "/api/wa/evento" and metodo == "POST":
        if not hmac.compare_digest(h.headers.get("X-WA-Token") or "", WA_TOKEN):
            h._envia(401, {"erro": "token inválido"}); return True
        ev = h._corpo()
        threading.Thread(target=wa_evento, args=(ev,), daemon=True).start()
        h._envia(200, {"ok": True}); return True
    if path == "/api/wa/status" and metodo == "GET":
        h._envia(200, wa_status()); return True
    if path == "/api/wa/conectar" and metodo == "POST":
        waha_garante_sessao(); h._envia(200, wa_status()); return True
    if path == "/api/wa/sair" and metodo == "POST":
        try:
            waha("POST", f"/api/sessions/{WAHA_SESSAO}/logout")
        except urllib.error.HTTPError:
            pass
        h._envia(200, {"ok": True}); return True
    if path == "/api/wa/enviar" and metodo == "POST":
        d = h._corpo()
        l = leads.get(d.get("lead_id") or "") or lead_por_numero(d.get("numero") or "")
        if not l:
            h._envia(400, {"erro": "Só envio para leads do CRM."}); return True
        if l.get("optout"):
            h._envia(400, {"erro": "Esse lead pediu para não receber mensagens."}); return True
        try:
            c = wa_enviar(l, d.get("texto"), numero=d.get("numero") or None)
        except ValueError as e:
            h._envia(400, {"erro": str(e)}); return True
        h._envia(200, {"conversa": c, "lead": l}); return True
    if path == "/api/conversas" and metodo == "GET":
        with lock:
            lista = sorted((resumo_conversa(c) for c in conversas.values()), key=lambda x: -(x["ultima_em"] or 0))
        h._envia(200, lista); return True
    m = re.fullmatch(r"/api/conversas/(\d+)(?:/(ia|lida))?", path)
    if m and m.group(1) in conversas:
        c = conversas[m.group(1)]
        if metodo == "GET" and not m.group(2):
            with lock:
                h._envia(200, resumo_conversa(c) | {"msgs": c["msgs"][-200:], "lead": leads.get(c["lead_id"])})
            return True
        if metodo == "POST" and m.group(2) == "lida":
            with lock:
                c["nao_lidas"] = 0
            salvar_conversas(); h._envia(200, {"ok": True}); return True
        if metodo == "POST" and m.group(2) == "ia":
            d = h._corpo()
            with lock:
                c["ia"] = bool(d.get("ativa"))
                c["ia_motivo"] = None if c["ia"] else "Desligada por você"
                c.pop("ia_erro", None)
                if c["ia"] and c["msgs"] and c["msgs"][-1]["de"] == "lead" and config["agente"].get("auto_responder"):
                    pendentes_ia[c["numero"]] = time.time() + 3
            salvar_conversas(); h._envia(200, resumo_conversa(c)); return True
    if path == "/api/agente" and metodo == "GET":
        h._envia(200, {"agente": config["agente"], "auto_envio": config["auto_envio"], "envios": envios,
                          "elegiveis": len(elegiveis()), "claude": bool(claude_bin()), "chave_api": bool(chave_api()),
                          "janela": na_janela(config["auto_envio"])})
        return True
    if path == "/api/agente" and metodo == "PUT":
        d = h._corpo()
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
        salvar_config(); h._envia(200, {"agente": config["agente"], "auto_envio": config["auto_envio"]}); return True
    if path == "/api/agente/primeira" and metodo == "POST":
        d = h._corpo()
        l = leads.get(d.get("lead_id") or "")
        if not l:
            h._envia(404, {"erro": "Lead não encontrado."}); return True
        try:
            h._envia(200, {"texto": primeira_mensagem(l, d.get("modo"))})
        except Exception as e:
            h._envia(500, {"erro": str(e)})
        return True
    if path == "/api/agente/simular" and metodo == "POST":
        # testa a IA sem enviar nada: conversa fictícia com um lead real
        d = h._corpo()
        l = leads.get(d.get("lead_id") or "") or next(iter(leads.values()), None)
        if not l:
            h._envia(400, {"erro": "Sem leads para simular."}); return True
        c = {"msgs": [{"t": time.time(), "de": m.get("de", "lead"), "txt": str(m.get("txt", ""))} for m in d.get("msgs", [])][-30:]}
        try:
            h._envia(200, ia_decide(l, c))
        except Exception as e:
            h._envia(500, {"erro": str(e)})
        return True
    if path == "/api/campanhas" and metodo == "GET":
        with lock:
            todos = [l for l in leads.values() if l.get("whatsapp")]
            cont = {sid: {"total": sum(1 for l in todos if SEGMENTOS[sid]["regra"](l)),
                          "na_fila": len(elegiveis(sid)) if config["campanhas"][sid].get("ativo") else 0} for sid in SEGMENTOS}
            fila_fu = sum(1 for c in conversas.values() if c.get("followups", 0) < len(config["followup"].get("dias") or [])
                          and not any(m["de"] == "lead" for m in c["msgs"])
                          and (leads.get(c["lead_id"]) or {}).get("status") == "contatado")
        h._envia(200, {"segmentos": [{"id": sid, "nome": s["nome"], "descricao": s["descricao"], **cont[sid],
                                         **config["campanhas"][sid]} for sid, s in SEGMENTOS.items()],
                          "followup": config["followup"], "followup_pendentes": fila_fu})
        return True
    if path == "/api/campanhas" and metodo == "PUT":
        d = h._corpo()
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
        salvar_config(); h._envia(200, {"ok": True}); return True
    if path == "/api/campanhas/previa" and metodo == "POST":
        d = h._corpo()
        sid = d.get("segmento")
        with lock:
            exemplos = [l for l in leads.values() if segmento_de(l, so_ativos=False) == sid] or list(leads.values())
        if not exemplos:
            h._envia(400, {"erro": "Sem leads para a prévia."}); return True
        l = leads.get(d.get("lead_id") or "") or random.choice(exemplos)
        h._envia(200, {"texto": preenche(str(d.get("texto") or ""), l), "lead": l.get("nome")}); return True
    if path == "/api/agenda" and metodo == "GET":
        try:
            dia = datetime.strptime((q.get("dia") or [""])[0], "%Y-%m-%d").date()
        except ValueError:
            dia = datetime.now(BR).date()
        with lock:
            rs = sorted((r for r in agenda_dados.get("reservas", []) if r.get("estado") != "cancelada"), key=lambda r: r["inicio"])
            h._envia(200, {"config": config["agenda"], "dia": dia.isoformat(), "slots": slots_do_dia(dia), "reservas": rs})
        return True
    if path == "/api/agenda/config" and metodo == "PUT":
        d = h._corpo()
        with lock:
            a = config["agenda"]
            if re.fullmatch(r"\d\d:\d\d", str(d.get("inicio", ""))): a["inicio"] = d["inicio"]
            if re.fullmatch(r"\d\d:\d\d", str(d.get("fim", ""))): a["fim"] = d["fim"]
            if "dias" in d: a["dias"] = sorted({int(x) for x in d["dias"] if 0 <= int(x) <= 6})
            if "duracao" in d: a["duracao"] = max(10, min(240, int(d["duracao"])))
            if "antecedencia_h" in d: a["antecedencia_h"] = max(0, min(72, float(d["antecedencia_h"])))
        salvar_config(); h._envia(200, config["agenda"]); return True
    if path == "/api/agenda/reservar" and metodo == "POST":
        d = h._corpo()
        l = leads.get(d.get("lead_id") or "")
        if not l:
            h._envia(404, {"erro": "Lead não encontrado."}); return True
        try:
            h._envia(200, reservar(l, str(d.get("inicio") or ""), "manual"))
        except ValueError as e:
            h._envia(409, {"erro": str(e)})
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
        h._envia(200 if r else 404, r or {"erro": "não encontrado"}); return True
    return False
