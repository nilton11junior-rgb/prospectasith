// Prospecta: Agente IA e disparo automático. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ AGENTE IA ═════════════
let AG = null, alvoAg = null, textoAg = "";
VIEWS.agente = async (leadId) => {
  crumbs([["Atendimento"],["Agente IA"]]);
  try{ AG = await api("/api/agente"); }catch(e){ return toast(e.message); }
  if(leadId) alvoAg = decodeURIComponent(leadId);
  if(rota().v!=="agente") return;
  const a = AG.agente, e = AG.auto_envio, tpls = S.config?.templates||[];
  const DIAS = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"];
  const buscasOk = S.buscas.filter(b=>b.estado==="concluida");
  const prox = AG.envios.proximo*1000 > Date.now() ? new Date(AG.envios.proximo*1000).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"}) : "agora";
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Agente de atendimento IA</h1><p>Treine a abordagem, escolha um alvo e aprove a primeira mensagem. A IA acompanha as respostas, marca a chamada na agenda e movimenta o funil.</p></div>
    <div class="acts"><a class="btn" href="#/whatsapp">${ic("wa")}Conversas</a><button class="btn pri" id="agSalva">${ic("check")}Salvar</button></div></div>
    ${AG.claude?"":`<div class="note err fade" style="margin-bottom:14px">${ic("flag")}<span>Claude Code não encontrado neste computador. Instale e faça login com <code>claude</code> para a IA funcionar (usa sua assinatura, sem chave de API).</span></div>`}
    <div class="grid g2 fade" style="align-items:start">
      <div class="card"><div class="card-h"><h3>${ic("spark")} Pré-treinamento</h3></div><div class="card-b">
        <p class="muted sm" style="margin-top:0">Descreva serviços, diferenciais, objeções e como marcar a chamada. A IA só apresenta o que estiver aqui.</p>
        <label class="lbl">Base de conhecimento <span class="muted" id="agN"></span></label>
        <textarea class="in" id="agBase" rows="12" maxlength="12000" style="width:100%" placeholder="Quem somos; o que vendemos; para quem; diferenciais; objeções comuns e respostas; quando passar para humano…">${esc(a.base)}</textarea>
        <label class="lbl">Instruções de abordagem</label>
        <textarea class="in" id="agInst" rows="4" maxlength="4000" style="width:100%" placeholder="Tom da conversa, como se apresentar (ex.: assistente virtual da equipe do Fulano), o que perguntar primeiro…">${esc(a.instrucoes)}</textarea>
        <div class="grid g2" style="gap:10px;margin-top:10px">
          <div><label class="lbl" style="margin-top:0">Modelo</label><select class="in" id="agMod" style="width:100%">${[["haiku","Haiku (rápido)"],["sonnet","Sonnet (recomendado)"],["opus","Opus (mais caprichado)"]].map(([v,n])=>`<option value="${v}" ${a.modelo===v?"selected":""}>${n}</option>`).join("")}</select></div>
          <div><label class="lbl" style="margin-top:0">Esperar antes de responder</label><select class="in" id="agEsp" style="width:100%">${[10,25,45,90].map(s=>`<option value="${s}" ${+a.espera_s===s?"selected":""}>${s} segundos</option>`).join("")}</select></div>
        </div>
        <label class="lbl">Motor da IA</label>
        <div class="sm muted">${AG.chave_api?`Usando sua <b>chave de API</b> da Anthropic (respostas em segundos).`:`Usando o <b>Claude Code</b> da sua assinatura (sem chave). Cada resposta leva de 20 s a 1 min.`}</div>
        <div class="row" style="margin-top:6px"><input class="in" type="password" id="agKey" placeholder="${AG.chave_api?"Chave salva — cole outra para trocar":"Opcional: chave sk-ant-… para responder mais rápido"}" style="flex:1" autocomplete="off">
          <button class="btn sm" id="agKeyB">${AG.chave_api?"Trocar":"Salvar chave"}</button>${AG.chave_api?`<button class="btn sm" id="agKeyX">Remover</button>`:""}</div>
        <div class="sep"></div>
        <label class="switch"><input type="checkbox" id="agAuto" ${a.auto_responder?"checked":""}> Responder automaticamente quando um lead do CRM mandar mensagem</label>
        <div class="hint">Só números exatos de leads das suas buscas. Conversas pessoais, grupos e números desconhecidos são ignorados. Se você responder pelo celular, a IA sai daquela conversa.</div>
      </div></div>
      <div class="grid" style="gap:16px">
        <div class="card"><div class="card-h"><h3>${ic("users")} Escolher alvo</h3></div><div class="card-b">
          <input class="in" id="agQ" type="search" placeholder="Nome, bairro ou telefone" style="width:100%">
          <div class="mini-l" id="agL" style="margin-top:8px;max-height:200px;overflow:auto"></div>
          <div id="agAlvo"></div>
        </div></div>
        <div class="card"><div class="card-h"><h3>${ic("send")} Disparo automático</h3><div class="sp"></div><label class="switch"><input type="checkbox" id="aeOn" ${e.ativo?"checked":""}> Ligado</label></div><div class="card-b">
          <div class="kv" style="margin-bottom:12px"><div><span class="xs muted">Enviadas hoje</span><b class="num">${AG.envios.n||0}/${e.limite_dia}</b></div><div><span class="xs muted">Na fila</span><b class="num">${fN(AG.elegiveis)}</b></div><div><span class="xs muted">Próximo envio</span><b class="num" style="font-size:15px">${e.ativo?(AG.janela?prox:"fora do horário"):"desligado"}</b></div></div>
          ${AG.envios.ultimo_erro?`<div class="note err" style="margin-bottom:10px">${ic("flag")}<span>${esc(AG.envios.ultimo_erro)}</span></div>`:""}
          <div class="grid g2" style="gap:10px">
            <div><label class="lbl" style="margin-top:0">Primeira mensagem</label><select class="in" id="aeModo" style="width:100%"><option value="template" ${e.modo==="template"?"selected":""}>Roteiros por segmento (Campanhas)</option><option value="ia" ${e.modo==="ia"?"selected":""}>IA escreve seguindo a estratégia do segmento</option></select>
              <div class="hint"><a href="#/campanhas">Editar segmentos e mensagens →</a></div></div>
            <div><label class="lbl" style="margin-top:0">Reserva (segmento sem roteiro)</label><select class="in" id="aeTpl" style="width:100%">${tpls.map(t=>`<option value="${esc(t.id)}" ${e.template===t.id?"selected":""}>${esc(t.nome)}</option>`).join("")}</select></div>
            <div><label class="lbl">Máximo por dia</label><input class="in" type="number" id="aeLim" min="1" max="200" value="${e.limite_dia}" style="width:100%"></div>
            <div><label class="lbl">Intervalo (minutos)</label><div class="row"><input class="in" type="number" id="aeMin" min="1" value="${Math.round(e.intervalo_min/60)}" style="width:70px"> a <input class="in" type="number" id="aeMax" min="1" value="${Math.round(e.intervalo_max/60)}" style="width:70px"></div></div>
            <div><label class="lbl">Horário</label><div class="row"><input class="in" type="time" id="aeIni" value="${e.hora_ini}"> às <input class="in" type="time" id="aeFim" value="${e.hora_fim}"></div></div>
          </div>
          <label class="lbl">Dias</label><div class="dias" id="aeDias">${DIAS.map((d,i)=>`<label><input type="checkbox" value="${i}" ${e.dias.includes(i)?"checked":""}>${d}</label>`).join("")}</div>
          <label class="lbl">Só leads destas buscas (vazio = todas)</label><div class="chips" id="aeBus">${buscasOk.map(b=>`<span class="chip ${e.buscas.includes(b.id)?"on":""}" data-b="${b.id}">${esc(b.parametros.nichos.join(", "))} · ${esc(b.parametros.cidade)}</span>`).join("")||'<span class="muted sm">Nenhuma busca concluída.</span>'}</div>
          <div class="note" style="margin-top:12px">${ic("flag")}<span>Envio em massa sem limite derruba o número. Comece com 20–30 por dia, intervalos de 2–5 min, e só para empresas. Quem pedir para parar sai da lista na hora.</span></div>
        </div></div>
        <div class="card"><div class="card-h"><h3>${ic("msg")} Testar a IA (não envia nada)</h3></div><div class="card-b">
          <textarea class="in" id="smT" rows="2" style="width:100%" placeholder="Escreva como se fosse o lead. Ex.: Oi, quanto custa um site?"></textarea>
          <div class="row" style="justify-content:flex-end;margin-top:8px"><button class="btn sm" id="smB">${ic("spark")}Simular resposta</button></div>
          <div id="smR"></div>
        </div></div>
      </div>
    </div>`;
  const cont = () => $("#agN").textContent = `(${fN($("#agBase").value.length)}/12.000)`; cont(); $("#agBase").oninput = cont;
  $$("#aeBus .chip").forEach(c => c.onclick = () => c.classList.toggle("on"));
  const coleta = () => ({agente:{base:$("#agBase").value, instrucoes:$("#agInst").value, modelo:$("#agMod").value, espera_s:+$("#agEsp").value, auto_responder:$("#agAuto").checked},
    auto_envio:{ativo:$("#aeOn").checked, modo:$("#aeModo").value, template:$("#aeTpl").value, limite_dia:+$("#aeLim").value,
      intervalo_min:Math.round(+$("#aeMin").value*60), intervalo_max:Math.round(+$("#aeMax").value*60), hora_ini:$("#aeIni").value, hora_fim:$("#aeFim").value,
      dias:$$("#aeDias input:checked").map(i=>+i.value), buscas:$$("#aeBus .chip.on").map(c=>c.dataset.b)}});
  $("#agKeyB").onclick = async () => { const k=$("#agKey").value.trim(); if(!k) return toast("Cole a chave.");
    try{ await api("/api/agente",{method:"PUT",body:{chave_api:k}}); toast("Chave salva"); VIEWS.agente(); }catch(err){ toast(err.message); } };
  $("#agKeyX") && ($("#agKeyX").onclick = async () => { await api("/api/agente",{method:"PUT",body:{chave_api:""}}); toast("Chave removida"); VIEWS.agente(); });
  $("#agSalva").onclick = async () => { try{ await api("/api/agente",{method:"PUT",body:coleta()}); toast("Agente salvo"); VIEWS.agente(); }catch(err){ toast(err.message); } };
  $("#aeOn").onchange = async ev => { if(ev.target.checked && !$("#agBase").value.trim() && $("#aeModo").value==="ia"){ toast("Preencha a base de conhecimento antes."); ev.target.checked=false; return; }
    try{ await api("/api/agente",{method:"PUT",body:coleta()}); toast(ev.target.checked?"Disparo automático ligado":"Disparo automático desligado"); VIEWS.agente(); }catch(err){ toast(err.message); } };
  const desenhaLista = () => { const q=semAc($("#agQ").value);
    const rows = S.leads.filter(l=>l.whatsapp && !l.optout && (!q || semAc(l.nome+" "+l.bairro+" "+l.whatsapp).includes(q))).slice(0,40);
    $("#agL").innerHTML = rows.map(l=>`<div class="it ${alvoAg===l.id?"on":""}" data-id="${esc(l.id)}">${ic("wa")}<b style="flex:1">${esc(l.nome)}</b><span class="xs muted">${esc(l.cidade||"")}</span>${pillSt(l.status)}</div>`).join("")||'<div class="muted sm">Nenhum lead com WhatsApp.</div>';
    $$("#agL .it").forEach(it => it.onclick = () => { alvoAg = it.dataset.id; textoAg=""; desenhaLista(); desenhaAlvo(); }); };
  const desenhaAlvo = () => { const l = S.map[alvoAg]; if(!l){ $("#agAlvo").innerHTML=""; return; }
    $("#agAlvo").innerHTML = `<div class="sep"></div><div class="row"><b>${esc(l.nome)}</b><span class="muted sm">${fTel(l.whatsapp)}</span></div>
      <div class="row" style="margin:8px 0"><button class="btn sm" id="pmT">Usar modelo</button><button class="btn sm" id="pmI">${ic("spark")}Escrever com IA</button></div>
      <textarea class="in" id="pmX" rows="4" style="width:100%" placeholder="Gere ou escreva a primeira mensagem…">${esc(textoAg)}</textarea>
      <div class="row" style="justify-content:flex-end;margin-top:8px"><button class="btn wa" id="pmE">${ic("send")}Aprovar e enviar</button></div>`;
    const gera = async modo => { $("#pmX").value = "Gerando…"; try{ textoAg = (await api("/api/agente/primeira",{method:"POST",body:{lead_id:l.id,modo}})).texto; }catch(err){ textoAg=""; toast(err.message); } $("#pmX").value = textoAg; };
    $("#pmT").onclick = () => gera("template"); $("#pmI").onclick = () => gera("ia");
    $("#pmX").oninput = ev => textoAg = ev.target.value;
    $("#pmE").onclick = async () => { const t=$("#pmX").value.trim(); if(!t) return toast("Escreva a mensagem.");
      if(!confirma("pm"+l.id,`Enviar para ${l.nome}?`)) return;
      $("#pmE").disabled = true;
      try{ const r = await api("/api/wa/enviar",{method:"POST",body:{lead_id:l.id,texto:t}}); upsertLead(r.lead); toast("Mensagem enviada"); location.hash = `#/whatsapp/${r.conversa.numero}`; }
      catch(err){ toast(err.message); $("#pmE").disabled=false; } }; };
  $("#agQ").oninput = desenhaLista; desenhaLista(); desenhaAlvo();
  $("#smB").onclick = async () => { const t=$("#smT").value.trim(); if(!t) return;
    $("#smR").innerHTML = `<div class="muted sm" style="margin-top:8px">A IA está pensando… (uns 20 s)</div>`;
    try{ await api("/api/agente",{method:"PUT",body:{agente:coleta().agente}});
      const r = await api("/api/agente/simular",{method:"POST",body:{lead_id:alvoAg, msgs:[{de:"lead",txt:t}]}});
      $("#smR").innerHTML = `<div class="wa-prev" style="margin-top:10px;min-height:0"><div class="bubble">${esc(r.mensagem||"(não responderia)")}</div></div>
        <div class="xs muted" style="margin-top:6px">Ação: <b>${esc(r.acao)}</b>${r.horario?` · horário ${esc(r.horario)}`:""}${r.resumo?` · ${esc(r.resumo)}`:""}</div>`; }
    catch(err){ $("#smR").innerHTML = `<div class="note err" style="margin-top:8px">${ic("flag")}<span>${esc(err.message)}</span></div>`; } };
};

