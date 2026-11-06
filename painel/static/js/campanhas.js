// Prospecta: Campanhas: segmentos, roteiros e follow-up. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ CAMPANHAS (segmentos + roteiros + follow-up) ═════════════
let CP = null, segAberto = null;
const VARS = ["gancho","saudacao","nome","cidade","bairro","categoria","elogio","nota","avaliacoes"];
VIEWS.campanhas = async () => {
  crumbs([["Atendimento"],["Campanhas"]]);
  try{ CP = await api("/api/campanhas"); }catch(e){ return toast(e.message); }
  if(rota().v!=="campanhas") return;
  segAberto = segAberto || CP.segmentos[0].id;
  const draw = () => {
    const s = CP.segmentos.find(x=>x.id===segAberto), fu = CP.followup;
    $("#page").innerHTML = `<div class="ph fade"><div><h1>Campanhas</h1><p>Cada empresa cai num segmento pela situação dela (site, Instagram, reputação). Cada segmento tem estratégia e roteiros próprios, e o disparo automático alterna entre as variações para não repetir o mesmo texto.</p></div>
      <div class="acts"><a class="btn" href="#/oportunidades">${ic("trend")}Priorizar leads</a><a class="btn" href="#/agente">${ic("send")}Disparo automático</a><button class="btn pri" id="cpSalva">${ic("check")}Salvar campanhas</button></div></div>
      <div class="grid fade" style="grid-template-columns:${innerWidth<860?"1fr":"minmax(0,300px) minmax(0,1fr)"};align-items:start">
        <div class="card tpl-list" style="overflow:hidden">${CP.segmentos.map((x,i)=>`<div class="it ${x.id===segAberto?"on":""}" data-s="${x.id}">
            <div class="row"><b>${i+1}. ${esc(x.nome)}</b><span class="pill ${x.ativo?"s-fechado":"s-descartado"} nodot" style="margin-left:auto">${x.ativo?"ligado":"desligado"}</span></div>
            <p>${fN(x.total)} com WhatsApp · ${fN(x.na_fila)} na fila</p></div>`).join("")}
          <div class="it ${segAberto==="followup"?"on":""}" data-s="followup"><div class="row"><b>Follow-up (sem resposta)</b><span class="pill ${fu.ativo?"s-fechado":"s-descartado"} nodot" style="margin-left:auto">${fu.ativo?"ligado":"desligado"}</span></div><p>${fN(CP.followup_pendentes)} conversas aguardando resposta</p></div>
        </div>
        <div class="card"><div class="card-b" style="padding:20px 22px">${segAberto==="followup"?`
          <div class="row"><h3 style="margin:0">Follow-up automático</h3><div class="sp"></div><label class="switch"><input type="checkbox" id="fuOn" ${fu.ativo?"checked":""}> Ligado</label></div>
          <p class="muted sm">Para quem recebeu a primeira mensagem e não respondeu. Para na hora em que o lead responde, pede para parar ou muda de etapa. Conta no limite diário do disparo.</p>
          ${fu.variantes.map((grupo,k)=>`<div class="sep"></div><div class="row"><b>${k+1}º follow-up</b><span class="muted sm">depois de</span><input class="in" type="number" min="1" max="60" data-fd="${k}" value="${fu.dias[k]??(k+1)*3}" style="width:70px"><span class="muted sm">dias da primeira mensagem</span></div>
            ${grupo.map((v,j)=>`<textarea class="in" rows="2" data-fv="${k}:${j}" style="width:100%;margin-top:8px">${esc(v)}</textarea>`).join("")}
            <button class="btn sm" data-fadd="${k}" style="margin-top:6px">${ic("plus")}Variação</button>`).join("")}`
          :`<div class="row"><h3 style="margin:0">${esc(s.nome)}</h3><div class="sp"></div><label class="switch"><input type="checkbox" id="sgOn" ${s.ativo?"checked":""}> Ligado</label></div>
          <p class="muted sm">${esc(s.descricao)} · ${fN(s.total)} leads com WhatsApp, ${fN(s.na_fila)} na fila do disparo.</p>
          <p class="sm"><a href="#/oportunidades/${encodeURIComponent(s.id)}">Ver oportunidades desta campanha →</a></p>
          <label class="lbl">Estratégia (a IA segue isto ao escrever e ao responder esse lead)</label>
          <textarea class="in" id="sgEst" rows="3" style="width:100%">${esc(s.estrategia)}</textarea>
          <label class="lbl">Variações da primeira mensagem <span class="muted">(o robô alterna entre elas)</span></label>
          <div id="sgVs">${s.variantes.map((v,j)=>`<div class="row" style="align-items:flex-start;margin-bottom:8px"><textarea class="in" rows="3" data-v="${j}" style="flex:1">${esc(v)}</textarea>
            <div style="display:flex;flex-direction:column;gap:4px"><button class="btn sm" data-prev="${j}">Prévia</button><button class="btn sm danger" data-del="${j}" ${s.variantes.length<2?"disabled":""}>${ic("trash")}</button></div></div>`).join("")}</div>
          <button class="btn sm" id="sgAdd">${ic("plus")}Nova variação</button>
          <div class="chips" style="margin-top:12px">${VARS.map(v=>`<span class="chip" data-var="${v}">+ {${v}}</span>`).join("")}</div>
          <div class="hint">{saudacao} = Bom dia/Boa tarde conforme a hora. {gancho} é a 1ª frase do elogio (“Vi que a X tem ótimas avaliações no Google.”; com nota menor fica neutra: “Vi a X aqui no Google.”). {elogio} é só o trecho “com ótimas/boas avaliações”. Clique numa variável para inserir no último campo usado.</div>
          <label class="lbl">Prévia com uma empresa real deste segmento</label>
          <div class="wa-prev"><div class="bubble" id="sgPrev">Clique em “Prévia”.</div></div><div class="xs muted" id="sgPrevL" style="margin-top:4px"></div>`}
        </div></div>
      </div>
      <div class="note fade" style="margin-top:14px">${ic("flag")}<span>A ordem importa: a empresa entra no primeiro segmento <b>ligado</b> que combina com ela. Ex.: com “Nota baixa” desligado, uma empresa sem site e com nota 3,5 vai para “Sem site e sem Instagram”. Sem link na primeira mensagem: isso reduz bloqueios.</span></div>`;
    $$(".tpl-list .it").forEach(it => it.onclick = () => { coleta(); segAberto = it.dataset.s; draw(); });
    let ultimoCampo = null;
    $$("textarea").forEach(t => t.addEventListener("focus", () => ultimoCampo = t));
    $$("[data-var]").forEach(c => c.onclick = () => { const ta = ultimoCampo || $("[data-v]"); if(!ta) return; const p=ta.selectionStart??ta.value.length, v=`{${c.dataset.var}}`;
      ta.value = ta.value.slice(0,p)+v+ta.value.slice(ta.selectionEnd??p); ta.focus(); ta.setSelectionRange(p+v.length,p+v.length); });
    if(segAberto==="followup"){
      $("#fuOn").onchange = e => fu.ativo = e.target.checked;
      $$("[data-fadd]").forEach(b => b.onclick = () => { coleta(); fu.variantes[+b.dataset.fadd].push(""); draw(); });
    } else {
      $("#sgOn").onchange = e => s.ativo = e.target.checked;
      $("#sgAdd").onclick = () => { coleta(); s.variantes.push(""); draw(); $$("[data-v]").pop().focus(); };
      $$("[data-del]").forEach(b => b.onclick = () => { coleta(); s.variantes.splice(+b.dataset.del,1); draw(); });
      $$("[data-prev]").forEach(b => b.onclick = async () => { const texto = $(`[data-v="${b.dataset.prev}"]`).value;
        try{ const r = await api("/api/campanhas/previa",{method:"POST",body:{segmento:s.id, texto}});
          $("#sgPrev").innerHTML = esc(r.texto)+`<small>${new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})} ✓✓</small>`; $("#sgPrevL").textContent = `Exemplo: ${r.lead}`; }catch(e){ toast(e.message); } });
    }
    $("#cpSalva").onclick = async () => { coleta();
      try{ await api("/api/campanhas",{method:"PUT",body:{campanhas:Object.fromEntries(CP.segmentos.map(x=>[x.id,{ativo:x.ativo,estrategia:x.estrategia,variantes:x.variantes}])), followup:CP.followup}});
        toast("Campanhas salvas"); VIEWS.campanhas(); }catch(e){ toast(e.message); } };
  };
  const coleta = () => {
    if(segAberto==="followup"){ const fu=CP.followup;
      $$("[data-fd]").forEach(i => fu.dias[+i.dataset.fd] = +i.value || 1);
      $$("[data-fv]").forEach(t => { const [k,j]=t.dataset.fv.split(":").map(Number); fu.variantes[k][j]=t.value; });
      fu.variantes = fu.variantes.map(g=>g.filter(v=>v.trim()||g.length===1));
    } else { const s = CP.segmentos.find(x=>x.id===segAberto); if(!s||!$("#sgEst")) return;
      s.estrategia = $("#sgEst").value; s.variantes = $$("[data-v]").map(t=>t.value); }
  };
  draw();
};

