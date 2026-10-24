"""Agenda de chamadas: horários livres pela disponibilidade e reservas sem conflito (horário de Brasília)."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from estado import ARQ_AGENDA, _grava, agenda_dados, config, lock, registrar, salvar_leads


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
