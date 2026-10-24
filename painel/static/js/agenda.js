// Prospecta: Agenda de atendimentos. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ AGENDA ═════════════
let diaAg = null, leadAgenda = null;
VIEWS.agenda = async () => {
  crumbs([["Atendimento"],["Agenda"]]);
  diaAg = diaAg || new Date(Date.now()-3*3600e3).toISOString().slice(0,10);
  let A; try{ A = await api(`/api/agenda?dia=${diaAg}`); }catch(e){ return toast(e.message); }
  if(rota().v!=="agenda") return;
  const c = A.config, DIAS = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"];
  const fdt = s => { const [d,h]=s.split(" "); const [y,m,dd]=d.split("-"); return `${dd}/${m} às ${h}`; };
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Agenda de atendimentos</h1><p>Horários de Brasília. A IA só oferece horários livres daqui, e cada reserva move o lead para “Reunião marcada”.</p></div>
    <div class="acts"><a class="btn" href="#/funil">${ic("kanban")}Ver funil</a></div></div>
    <div class="grid g2 fade" style="align-items:start">
      <div class="card"><div class="card-h"><h3>${ic("cal")} Disponibilidade</h3></div><div class="card-b">
        <label class="lbl" style="margin-top:0">Dias com atendimento</label><div class="dias" id="agD">${DIAS.map((d,i)=>`<label><input type="checkbox" value="${i}" ${c.dias.includes(i)?"checked":""}>${d}</label>`).join("")}</div>
        <div class="grid g2" style="gap:10px">
          <div><label class="lbl">Início</label><input class="in" type="time" id="agI" value="${c.inicio}" style="width:100%"></div>
          <div><label class="lbl">Fim</label><input class="in" type="time" id="agF" value="${c.fim}" style="width:100%"></div>
          <div><label class="lbl">Duração</label><select class="in" id="agDu" style="width:100%">${[15,20,30,45,60,90].map(m=>`<option value="${m}" ${+c.duracao===m?"selected":""}>${m} min</option>`).join("")}</select></div>
          <div><label class="lbl">Antecedência mínima</label><select class="in" id="agAn" style="width:100%">${[0,1,2,4,12,24].map(h=>`<option value="${h}" ${+c.antecedencia_h===h?"selected":""}>${h} h</option>`).join("")}</select></div>
        </div>
        <div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn sm pri" id="agS">${ic("check")}Salvar disponibilidade</button></div>
        <div class="sep"></div>
        <label class="lbl" style="margin-top:0">Dia do atendimento</label><input class="in" type="date" id="agDia" value="${A.dia}">
        <div class="hint">Horários livres para reservas manuais ou pelo agente IA. ${leadAgenda?"Clique num horário para reservar.":"Escolha um lead ao lado para reservar."}</div>
        <div class="slots" id="agSl">${A.slots.map(s=>`<span class="slot" data-s="${s}">${s.slice(11)}</span>`).join("")||'<span class="muted sm">Nenhum horário livre neste dia.</span>'}</div>
      </div></div>
      <div class="grid" style="gap:16px">
        <div class="card"><div class="card-h"><h3>${ic("users")} Agendar cliente</h3></div><div class="card-b">
          <input class="in" id="alQ" type="search" placeholder="Pesquisar lead por nome" style="width:100%">
          <div class="mini-l" id="alL" style="margin-top:8px;max-height:220px;overflow:auto"></div>
        </div></div>
        <div class="card"><div class="card-h"><h3>Compromissos</h3></div><div class="card-b">${A.reservas.length?A.reservas.map(r=>`<div class="row" style="padding:8px 0;border-bottom:1px solid var(--line-2)">
            <div style="flex:1"><b style="cursor:pointer" data-lead="${esc(r.lead_id)}">${esc(r.nome)}</b><div class="xs muted">${fdt(r.inicio)} · ${r.duracao} min · ${r.origem==="ia"?"marcado pela IA":"manual"}</div></div>
            <button class="btn sm" data-cancel="${r.id}">Cancelar</button></div>`).join(""):'<span class="muted sm">Nenhum compromisso.</span>'}</div></div>
      </div>
    </div>`;
  $("#agS").onclick = async () => { try{ await api("/api/agenda/config",{method:"PUT",body:{dias:$$("#agD input:checked").map(i=>+i.value), inicio:$("#agI").value, fim:$("#agF").value, duracao:+$("#agDu").value, antecedencia_h:+$("#agAn").value}}); toast("Disponibilidade salva"); VIEWS.agenda(); }catch(e){ toast(e.message); } };
  $("#agDia").onchange = e => { diaAg = e.target.value; VIEWS.agenda(); };
  const lista = () => { const q=semAc($("#alQ").value);
    const rows = S.leads.filter(l=>!q || semAc(l.nome+" "+l.bairro).includes(q)).sort((a,b)=>(a.status==="respondeu"?-1:0)-(b.status==="respondeu"?-1:0)).slice(0,30);
    $("#alL").innerHTML = rows.map(l=>`<div class="it ${leadAgenda===l.id?"on":""}" data-id="${esc(l.id)}"><b style="flex:1">${esc(l.nome)}</b><span class="xs muted">${esc(l.cidade||"")}${l.whatsapp?" · WhatsApp":""}</span>${pillSt(l.status)}</div>`).join("");
    $$("#alL .it").forEach(it => it.onclick = () => { leadAgenda = it.dataset.id; lista(); toast("Agora clique num horário livre"); }); };
  $("#alQ").oninput = lista; lista();
  $$("#agSl .slot").forEach(s => s.onclick = async () => { const l=S.map[leadAgenda]; if(!l) return toast("Escolha um lead primeiro.");
    if(!confirma("res"+s.dataset.s,`Reservar ${fdt(s.dataset.s)} para ${l.nome}?`)) return;
    try{ await api("/api/agenda/reservar",{method:"POST",body:{lead_id:l.id,inicio:s.dataset.s}}); await carregaLeads(); toast("Reserva confirmada"); VIEWS.agenda(); }catch(e){ toast(e.message); } });
  $$("[data-cancel]").forEach(b => b.onclick = async () => { if(!confirma("can"+b.dataset.cancel,"Cancelar este compromisso?")) return;
    await api(`/api/agenda/${b.dataset.cancel}/cancelar`,{method:"POST"}); toast("Cancelado"); VIEWS.agenda(); });
  $$("[data-lead]").forEach(b => b.onclick = () => abreLead(b.dataset.lead));
};

