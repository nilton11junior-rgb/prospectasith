// Prospecta: tabela de leads, ficha do lead e funil. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ LEADS (tabela reutilizável) ═════════════
const FL = ls.get("fl", {texto:"", wa:false, email:false, semsite:false, nota4:false, status:"", cidade:"", categoria:"", ocultarFechados:true, ocultarDescartados:false});
const TB = {ordem:{c:"nota",d:-1}, pag:0, sel:new Set()};
const POR_PAG = 50;

function botaoExcluirLead(id){
  return `<button class="btn danger sm busca-excluir" type="button" data-excluir-lead="${esc(id)}">${ic("trash")}Excluir lead</button>`;
}

function confirmarExclusaoLead(id){
  const lead = leadAberto?.id === id ? leadAberto : S.map[id];
  if(!lead || $("dialog[open]")) return;

  const dialog = document.createElement("dialog");
  dialog.className = "exclusao-dialog";
  dialog.setAttribute("aria-labelledby", "excluirLeadTitulo");
  dialog.innerHTML = `<form method="dialog">
    <div class="exclusao-body">
      <h2 id="excluirLeadTitulo">Excluir lead?</h2>
      <p><strong>${esc(lead.nome)}</strong> será removido da base, do funil e dos resultados das buscas, junto das conversas e reservas vinculadas no CRM.</p>
      <p class="muted sm">O CRM cria um backup local antes de apagar.</p>
      <p class="exclusao-erro" role="alert"></p>
    </div>
    <div class="exclusao-rodape">
      <button class="btn" autofocus>Cancelar</button>
      <button class="btn danger" type="button" id="confirmarExcluirLead">Excluir lead</button>
    </div>
  </form>`;
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();

  const confirmar = $("#confirmarExcluirLead", dialog);
  const cancelar = $("button[autofocus]", dialog);
  dialog.addEventListener("cancel", e => {
    if(cancelar.disabled) e.preventDefault();
  });
  confirmar.onclick = async () => {
    confirmar.disabled = cancelar.disabled = true;
    confirmar.textContent = "Excluindo…";
    try{
      await api(`/api/leads/${encodeURIComponent(id)}`, {method:"DELETE"});
    }catch(e){
      $(".exclusao-erro", dialog).textContent = e.message;
      confirmar.disabled = cancelar.disabled = false;
      confirmar.textContent = "Excluir lead";
      return;
    }
    delete S.map[id];
    S.leads = S.leads.filter(item => item.id !== id);
    TB.sel.delete(id);
    await Promise.all([carregaBuscas(), carregaConversas(), carregaLixeira()]);
    if(leadAberto?.id === id) fechaLead();
    dialog.close();
    render();
    toast("Lead excluído");
  };
}

document.addEventListener("click", e => {
  const botao = e.target.closest("[data-excluir-lead]");
  if(botao) confirmarExclusaoLead(botao.dataset.excluirLead);
});

VIEWS.leads = () => {
  crumbs([["Prospecção","#/buscas"],["Leads"]]);
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Leads</h1><p>Todas as empresas encontradas, sem repetição. Clique em uma para abrir a ficha.</p></div>
    <div class="acts"><button class="btn" id="bCopia">${ic("copy")}Copiar WhatsApps</button><button class="btn" id="bExp">${ic("down")}Exportar para Excel</button></div></div>
    <div class="card fade" id="tbl"></div>`;
  tabelaLeads($("#tbl"), () => S.leads, "todos", true);
};
function filtra(rows){
  const q = semAc(FL.texto);
  return rows.filter(l => (!q || semAc(`${l.nome} ${l.categoria} ${l.bairro} ${l.cidade} ${l.obs} ${l.telefone}`).includes(q)) &&
    (!FL.wa||l.whatsapp) && (!FL.email||l.email) && (!FL.semsite||!l.site) && (!FL.nota4||l.nota>=4) &&
    (!FL.status||l.status===FL.status) && (!FL.cidade||l.cidade===FL.cidade) && (!FL.categoria||l.categoria===FL.categoria) &&
    (!FL.ocultarFechados||!l.fechado) && (!FL.ocultarDescartados||l.status!=="descartado"));
}
function ordena(rows){ const {c,d} = TB.ordem;
  return [...rows].sort((a,b)=>{ let x=a[c], y=b[c];
    if(c==="contato"){ x=(!!a.whatsapp)*2+(!!a.email); y=(!!b.whatsapp)*2+(!!b.email); }
    if(c==="status"){ x=STATUS.findIndex(s=>s[0]===a.status); y=STATUS.findIndex(s=>s[0]===b.status); }
    if(c==="nota"&&x===y){ x=a.avaliacoes; y=b.avaliacoes; }
    return d*(typeof x==="number"||typeof y==="number" ? (x||0)-(y||0) : String(x||"").localeCompare(String(y||""),"pt-BR")); }); }
function tabelaLeads(el, fonte, chave, comAcoesTopo){
  if(TB.chave!==chave){ TB.chave=chave; TB.pag=0; TB.sel.clear(); }
  const opts = campo => [...new Set(fonte().map(l=>l[campo]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"pt-BR"));
  const draw = () => {
    const todos = fonte(), rows = ordena(filtra(todos)), pags = Math.max(1,Math.ceil(rows.length/POR_PAG));
    if(TB.pag>=pags) TB.pag = pags-1;
    const vis = rows.slice(TB.pag*POR_PAG, TB.pag*POR_PAG+POR_PAG);
    const th = (c,t) => `<th data-o="${c}">${t}${TB.ordem.c===c?(TB.ordem.d>0?" ↑":" ↓"):""}</th>`;
    const todosSel = vis.length && vis.every(l=>TB.sel.has(l.id));
    el.innerHTML = `
      <div class="tbar">
        <input class="in" type="search" id="fq" placeholder="Filtrar por nome, bairro, telefone…" value="${esc(FL.texto)}">
        <select class="in" id="fst"><option value="">Todos os status</option>${STATUS.map(([v,n])=>`<option value="${v}" ${FL.status===v?"selected":""}>${n}</option>`).join("")}</select>
        <select class="in" id="fcid"><option value="">Todas as cidades</option>${opts("cidade").map(c=>`<option ${FL.cidade===c?"selected":""}>${esc(c)}</option>`).join("")}</select>
        <select class="in" id="fcat"><option value="">Todas as categorias</option>${opts("categoria").map(c=>`<option ${FL.categoria===c?"selected":""}>${esc(c)}</option>`).join("")}</select>
        <span class="chip ${FL.wa?"on":""}" data-f="wa">${ic("wa")}WhatsApp</span>
        <span class="chip ${FL.email?"on":""}" data-f="email">${ic("mail")}E-mail</span>
        <span class="chip ${FL.semsite?"on":""}" data-f="semsite" title="Ótimo para quem vende site, tráfego ou marketing">Sem site</span>
        <span class="chip ${FL.nota4?"on":""}" data-f="nota4">★ 4+</span>
        <span class="chip ${FL.ocultarDescartados?"on":""}" data-f="ocultarDescartados">Ocultar descartados</span>
      </div>
      ${TB.sel.size?`<div class="bulk">${fN(TB.sel.size)} selecionado${TB.sel.size>1?"s":""}
        <select class="in" id="bulkSt" style="padding:5px 26px 5px 10px"><option value="">Mudar status para…</option>${STATUS.map(([v,n])=>`<option value="${v}">${n}</option>`).join("")}</select>
        <button class="btn sm" id="bulkExp">${ic("down")}Exportar seleção</button><button class="btn sm ghost" id="bulkClr">Limpar seleção</button></div>`:""}
      <div class="twrap"><table class="t"><thead><tr><th class="chk"><input type="checkbox" id="selAll" ${todosSel?"checked":""}></th>
        ${th("nome","Empresa")}${th("bairro","Local")}${th("telefone","Telefone")}${th("contato","Canais")}${th("nota","Nota")}${th("status","Status")}${th("atualizado_em","Atualizado")}</tr></thead>
      <tbody>${vis.map(l=>`<tr data-id="${esc(l.id)}" class="${TB.sel.has(l.id)?"sel":""}">
        <td class="chk"><input type="checkbox" data-sel="${esc(l.id)}" ${TB.sel.has(l.id)?"checked":""}></td>
        <td><div class="lead-n">${esc(l.nome)}</div><div class="lead-c">${esc(l.categoria)}${l.fechado?' · <b style="color:var(--err)">fechado</b>':""}</div>${botaoExcluirLead(l.id)}</td>
        <td><div class="sm">${esc(l.bairro||"—")}</div><div class="lead-c">${esc([l.cidade,l.uf].filter(Boolean).join(" - "))}</div></td>
        <td class="num sm" style="white-space:nowrap">${esc(l.telefone||"—")}</td>
        <td><div class="ok-ico"><span class="wa ${l.whatsapp?"on":""}" title="WhatsApp">${ic("wa")}</span><span class="em ${l.email?"on":""}" title="E-mail">${ic("mail")}</span><span class="ws ${l.site?"on":""}" title="Site">${ic("globe")}</span><span class="ig ${l.instagram?"on":""}" title="Instagram">${ic("ig")}</span></div></td>
        <td class="num" style="white-space:nowrap">${l.nota?`<span class="stars">★</span> ${fNota(l.nota)} <span class="muted xs">(${fN(l.avaliacoes)})</span>`:'<span class="muted">—</span>'}</td>
        <td>${pillSt(l.status)}</td>
        <td class="muted xs" style="white-space:nowrap">${fRel(l.atualizado_em)}</td></tr>`).join("")}</tbody></table>
      ${!rows.length?`<div class="empty"><div class="ic">${ic("search")}</div><b>${todos.length?"Nenhum lead com esses filtros":"Nenhum lead ainda"}</b>${todos.length?"Tente tirar algum filtro.":`<a href="#/nova">Faça uma busca</a> para começar.`}</div>`:""}</div>
      ${rows.length?`<div class="pag"><span>${fN(TB.pag*POR_PAG+1)}–${fN(TB.pag*POR_PAG+vis.length)} de ${fN(rows.length)} leads${rows.length!==todos.length?` (filtrados de ${fN(todos.length)})`:""}</span>
        ${pags>1?`<span class="row"><button class="btn sm" id="pA" ${TB.pag?"":"disabled"}>← Anterior</button><span>Página ${TB.pag+1} de ${pags}</span><button class="btn sm" id="pP" ${TB.pag<pags-1?"":"disabled"}>Próxima →</button></span>`:""}</div>`:""}`;
    const salva = () => { ls.set("fl",FL); TB.pag=0; draw(); };
    $("#fq",el).oninput = e => { FL.texto=e.target.value; ls.set("fl",FL); TB.pag=0; clearTimeout(draw.t); draw.t=setTimeout(()=>{ const pos=e.target.selectionStart; draw(); const f=$("#fq",el); f.focus(); f.setSelectionRange(pos,pos); },200); };
    $("#fst",el).onchange = e => { FL.status=e.target.value; salva(); };
    $("#fcid",el).onchange = e => { FL.cidade=e.target.value; salva(); };
    $("#fcat",el).onchange = e => { FL.categoria=e.target.value; salva(); };
    $$("[data-f]",el).forEach(c => c.onclick = () => { FL[c.dataset.f]=!FL[c.dataset.f]; salva(); });
    $$("th[data-o]",el).forEach(t => t.onclick = () => { const c=t.dataset.o; TB.ordem = {c, d: TB.ordem.c===c ? -TB.ordem.d : (["nota","atualizado_em","contato"].includes(c)?-1:1)}; draw(); });
    $("#selAll",el).onchange = e => { vis.forEach(l=> e.target.checked ? TB.sel.add(l.id) : TB.sel.delete(l.id)); draw(); };
    $$("tbody tr",el).forEach(tr => tr.onclick = e => {
      if(e.target.matches("input[type=checkbox]")){ const id=e.target.dataset.sel; e.target.checked?TB.sel.add(id):TB.sel.delete(id); draw(); return; }
      if(e.target.closest(".chk, [data-excluir-lead]")) return;
      abreLead(tr.dataset.id); });
    $("#pA",el) && ($("#pA",el).onclick = () => { TB.pag--; draw(); });
    $("#pP",el) && ($("#pP",el).onclick = () => { TB.pag++; draw(); });
    $("#bulkClr",el) && ($("#bulkClr",el).onclick = () => { TB.sel.clear(); draw(); });
    $("#bulkExp",el) && ($("#bulkExp",el).onclick = () => exportaCsv(ordena(fonte()).filter(l=>TB.sel.has(l.id)), "selecao"));
    $("#bulkSt",el) && ($("#bulkSt",el).onchange = async e => { const st=e.target.value; if(!st) return;
      const r = await api("/api/leads/lote",{method:"POST",body:{ids:[...TB.sel],status:st}}); await carregaLeads(); TB.sel.clear(); toast(`${fN(r.alterados)} leads → ${NOME_ST[st]}`); draw(); });
    if(comAcoesTopo){
      $("#bExp").onclick = () => exportaCsv(rows, "leads");
      $("#bCopia").onclick = () => copiaWhats(rows);
    }
  };
  el._draw = draw; draw();
}

// ═════════════ FICHA DO LEAD (gaveta lateral) ═════════════
let leadAberto = null;
async function abreLead(id){
  let l; try{ l = await api(`/api/leads/${encodeURIComponent(id)}`); }catch{ return toast("Lead não encontrado"); }
  leadAberto = l; desenhaLead(); $("#drawer").classList.add("on"); $("#ov").classList.add("on");
}
VIEWS.lead = id => { history.replaceState(null, "", "#/leads"); render(); abreLead(decodeURIComponent(id)); };
function fechaLead(){ $("#drawer").classList.remove("on"); $("#ov").classList.remove("on"); leadAberto=null;
  const t=$("#tbl"); if(t&&t._draw) t._draw(); if(rota().v==="funil"&&VIEWS.funil._draw) VIEWS.funil._draw(); }
$("#ov").onclick = fechaLead;
document.addEventListener("keydown", e => { if(e.key==="Escape" && leadAberto && !$("dialog[open]")) fechaLead(); });
function desenhaLead(){
  const l = leadAberto, tpls = S.config?.templates||[], tplSel = ls.get("tplSel", S.config?.padrao);
  const icEv = {whatsapp:"wa",status:"flag",nota:"note",ligacao:"phone",email:"mail",criado:"spark"};
  const origemWa = {site:"encontrado no site da empresa", maps:"informado no Google Maps", telefone:"o telefone é celular"}[l.whatsapp_origem]||"";
  const num = l.whatsapp || (l.tel_tipo==="fixo" ? l.tel_digitos : "");
  $("#drawer").innerHTML = `
    <button class="btn ghost sm dr-x" id="drX" aria-label="Fechar">${ic("x")}</button>
    <div class="dr-h">
      <div class="row" style="margin-bottom:8px">${pillSt(l.status)}${l.fechado?'<span class="pill s-descartado nodot">Fechado permanentemente</span>':""}</div>
      <h2>${esc(l.nome)}</h2>
      <div class="muted sm" style="margin-top:4px">${esc(l.categoria)}${l.nota?` · <span class="stars">★</span> ${fNota(l.nota)} (${fN(l.avaliacoes)} avaliações)`:""}</div>
      ${botaoExcluirLead(l.id)}
    </div>
    <div class="dr-b">
      ${num?`<div class="row" style="gap:8px;margin-bottom:6px">
          ${tpls.length?`<select class="in" id="tplSel" style="flex:1;min-width:0">${tpls.map(t=>`<option value="${esc(t.id)}" ${t.id===tplSel?"selected":""}>${esc(t.nome)}</option>`).join("")}</select>`:""}
          <a class="btn wa" id="drWa" href="#" target="_blank" rel="noopener">${ic("wa")}${l.whatsapp?"Chamar no WhatsApp":"Tentar WhatsApp"}</a></div>
        <div class="hint" style="margin:0 0 14px">${l.whatsapp?`${fTel(l.whatsapp)} · ${origemWa}`:"Telefone fixo: muitas empresas usam WhatsApp Business no fixo."}</div>
        <div class="row" style="gap:8px;margin-bottom:14px">
          ${(S.conversas||[]).find(c=>c.lead_id===l.id)?`<a class="btn sm" href="#/whatsapp/${(S.conversas||[]).find(c=>c.lead_id===l.id).numero}">${ic("msg")}Abrir conversa</a>`:""}
          <a class="btn sm" href="#/agente/${encodeURIComponent(l.id)}">${ic("spark")}Atender com IA</a>
          <a class="btn sm" href="#/agenda">${ic("cal")}Agendar</a></div>
        ${l.optout?`<div class="note err" style="margin-bottom:14px">${ic("flag")}<span>Pediu para não receber mensagens.</span></div>`:""}
        ${l.reuniao?`<div class="note info" style="margin-bottom:14px">${ic("cal")}<span>Chamada marcada: ${esc(l.reuniao.split(" ").reverse().join(" · "))}</span></div>`:""}`:""}
      <div class="acts-grid">
        ${l.tel_digitos?`<a class="btn" href="tel:+${esc(l.tel_digitos)}" data-ev="ligacao">${ic("phone")}Ligar</a>`:`<button class="btn" disabled>${ic("phone")}Ligar</button>`}
        ${l.email?`<a class="btn" href="mailto:${esc(l.email.split(",")[0].trim())}" data-ev="email">${ic("mail")}E-mail</a>`:`<button class="btn" disabled>${ic("mail")}E-mail</button>`}
        ${urlSegura(l.maps)?`<a class="btn" href="${esc(urlSegura(l.maps))}" target="_blank" rel="noopener">${ic("pin")}Maps</a>`:`<button class="btn" disabled>${ic("pin")}Maps</button>`}
      </div>
      <div class="sec-t">Etapa do funil</div>
      <div class="stsel" id="stsel">${STATUS.map(([v,n])=>`<button data-st="${v}" class="${l.status===v?"on s-"+v:""}">${n}</button>`).join("")}</div>
      <div class="sec-t">Dados</div>
      <dl class="info">
        <dt>Telefone</dt><dd class="num">${esc(l.telefone||"—")} ${l.tel_tipo?`<span class="pill nodot">${l.tel_tipo}</span>`:""}</dd>
        ${l.whatsapp&&l.whatsapp!==l.tel_digitos?`<dt>WhatsApp</dt><dd class="num">${fTel(l.whatsapp)}</dd>`:""}
        <dt>E-mail</dt><dd>${l.email?esc(l.email):'<span class="muted">não encontrado</span>'}</dd>
        <dt>Site</dt><dd>${l.site?`<a href="${esc(urlSegura(l.site))}" target="_blank" rel="noopener">${esc(dominio(l.site))}</a>`:'<span style="color:var(--warn);font-weight:600">Não tem site</span>'}</dd>
        ${l.instagram?`<dt>Instagram</dt><dd><a href="${esc(urlSegura(l.instagram))}" target="_blank" rel="noopener">${esc(l.instagram.replace(/^https?:\/\/(www\.)?instagram\.com\//,"@").replace(/\/$/,""))}</a></dd>`:""}
        ${l.facebook?`<dt>Facebook</dt><dd><a href="${esc(urlSegura(l.facebook))}" target="_blank" rel="noopener">${esc(l.facebook.replace(/^https?:\/\/(www\.|m\.)?facebook\.com\//,""))}</a></dd>`:""}
        ${l.linkedin?`<dt>LinkedIn</dt><dd><a href="${esc(urlSegura(l.linkedin))}" target="_blank" rel="noopener">abrir perfil</a></dd>`:""}
        <dt>Endereço</dt><dd>${esc(l.endereco||"—")}</dd>
        <dt>Bairro</dt><dd>${esc(l.bairro||"—")}</dd>
        <dt>Cidade</dt><dd>${esc([l.cidade,l.uf].filter(Boolean).join(" - ")||"—")}${l.cep?` · CEP ${esc(l.cep)}`:""}</dd>
        ${l.segmento?`<dt>Segmento</dt><dd><a href="#/campanhas">${esc(SEG_NOME[l.segmento]||l.segmento)}</a></dd>`:""}
        <dt>Origem</dt><dd>${(l.buscas||[]).map(bid=>{ const b=S.buscas.find(x=>x.id===bid); return b?`<a href="#/buscas/${bid}">${esc(b.parametros.nichos.join(", "))}</a>`:""; }).filter(Boolean).join(", ")||esc(l.nicho||"—")}</dd>
      </dl>
      <div class="sec-t">Anotações e histórico</div>
      <textarea class="in" id="nota" rows="2" placeholder="Ex.: falei com a recepcionista, retornar na segunda…"></textarea>
      <div class="row" style="justify-content:flex-end;margin-top:8px"><button class="btn sm pri" id="bNota">${ic("note")}Adicionar anotação</button></div>
      <div class="tl" style="margin-top:14px">${[...(l.historico||[])].reverse().map(e=>`<div class="tl-i"><div class="tl-d">${ic(icEv[e.tipo]||"note")}</div><div><div class="tl-t">${esc(e.tipo==="whatsapp"?"Chamado no WhatsApp":e.tipo==="ligacao"?"Ligação":e.tipo==="email"?"E-mail enviado":e.txt)}</div><div class="tl-m">${fData(e.t)}</div></div></div>`).join("")}</div>
    </div>`;
  $("#drX").onclick = fechaLead;
  const wa = $("#drWa");
  if(wa){
    const atual = () => tpls.find(t=>t.id===($("#tplSel")?.value||tplSel)) || tpls[0];
    const href = () => `https://wa.me/${num}?text=${encodeURIComponent(preencheTpl(atual()?.texto||"", l))}`;
    wa.href = href();
    $("#tplSel") && ($("#tplSel").onchange = e => { ls.set("tplSel", e.target.value); wa.href = href(); });
    wa.onclick = () => { wa.href = href(); registraEv("whatsapp"); };
  }
  $$("[data-ev]", $("#drawer")).forEach(a => a.addEventListener("click", () => registraEv(a.dataset.ev)));
  $("#stsel").onclick = async e => { const st=e.target.dataset.st; if(!st||st===l.status) return;
    leadAberto = await api(`/api/leads/${encodeURIComponent(l.id)}`,{method:"PATCH",body:{status:st}}); upsertLead(leadAberto); desenhaLead(); toast(`→ ${NOME_ST[st]}`); };
  $("#bNota").onclick = async () => { const t=$("#nota").value.trim(); if(!t) return;
    leadAberto = await api(`/api/leads/${encodeURIComponent(l.id)}/evento`,{method:"POST",body:{tipo:"nota",txt:t}}); upsertLead(leadAberto); desenhaLead(); toast("Anotação salva"); };
}
async function registraEv(tipo){
  const l = leadAberto; if(!l) return;
  try{ const novo = await api(`/api/leads/${encodeURIComponent(l.id)}/evento`,{method:"POST",body:{tipo}}); upsertLead(novo);
    if(leadAberto && leadAberto.id===novo.id){ leadAberto = novo; setTimeout(desenhaLead, 300); } }catch{}
}
function preencheTpl(t, l){ return String(t||"").replace(/\{nome\}/g, l.nome||"").replace(/\{cidade\}/g, l.cidade||"")
  .replace(/\{bairro\}/g, l.bairro||"").replace(/\{categoria\}/g, (l.categoria||"").toLowerCase()); }

// ═════════════ FUNIL (quadro) ═════════════
const FK = ls.get("fk", {busca:"", wa:false, texto:""});
VIEWS.funil = () => {
  crumbs([["Prospecção","#/buscas"],["Funil de vendas"]]);
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Funil de vendas</h1><p>Arraste os cartões entre as colunas para mudar a etapa. Clique para abrir a ficha.</p></div></div>
    <div class="row fade" style="flex-wrap:wrap;margin-bottom:14px">
      <input class="in" type="search" id="kq" placeholder="Filtrar…" style="max-width:240px" value="${esc(FK.texto)}">
      <select class="in" id="kb"><option value="">Todas as buscas</option>${S.buscas.filter(b=>b.estado==="concluida").map(b=>`<option value="${b.id}" ${FK.busca===b.id?"selected":""}>${esc(b.parametros.nichos.join(", "))} · ${esc(b.parametros.cidade)}</option>`).join("")}</select>
      <span class="chip ${FK.wa?"on":""}" id="kwa">${ic("wa")}Só com WhatsApp</span>
    </div><div class="kb fade" id="kbd"></div>`;
  const draw = () => {
    if(!$("#kbd")) return;
    const q = semAc(FK.texto);
    const rows = S.leads.filter(l => (!FK.busca || (l.buscas||[]).includes(FK.busca)) && (!FK.wa||l.whatsapp) && (!q || semAc(l.nome+" "+l.bairro+" "+l.categoria).includes(q)));
    $("#kbd").innerHTML = STATUS.map(([st,n]) => {
      // "Novo": os mais promissores primeiro (nota ponderada pelo nº de avaliações); demais: mais recentes primeiro
      const col = rows.filter(l=>l.status===st).sort((a,b)=> st==="novo" ? (b.nota*Math.log10(b.avaliacoes+1))-(a.nota*Math.log10(a.avaliacoes+1)) : (b.atualizado_em||0)-(a.atualizado_em||0));
      const lim = st==="novo"||st==="descartado" ? 40 : 200;
      return `<div class="kcol" data-st="${st}"><div class="kcol-h"><span class="dot" style="background:${COR_ST[st]};box-shadow:none"></span>${n}<span class="c num">${fN(col.length)}</span></div>
        <div class="kcol-b">${col.slice(0,lim).map(l=>`<div class="kc" draggable="true" data-id="${esc(l.id)}"><div class="n">${esc(l.nome)}</div><div class="m">${esc(l.categoria)}${l.bairro?" · "+esc(l.bairro):""}</div>
          <div class="f"><div class="ok-ico"><span class="wa ${l.whatsapp?"on":""}">${ic("wa")}</span><span class="em ${l.email?"on":""}">${ic("mail")}</span><span class="ws ${l.site?"on":""}">${ic("globe")}</span></div>${l.nota?`<span class="xs" style="margin-left:auto"><span class="stars">★</span> ${fNota(l.nota)}</span>`:""}</div>${botaoExcluirLead(l.id)}</div>`).join("")}
          ${col.length>lim?`<div class="kmore">+ ${fN(col.length-lim)} — use os filtros ou a tela de Leads</div>`:""}
          ${!col.length?`<div class="kmore">Arraste para cá</div>`:""}</div></div>`; }).join("");
    let arrastando = null;
    $$(".kc").forEach(c => { c.ondragstart = e => { arrastando=c.dataset.id; c.classList.add("drag"); e.dataTransfer.effectAllowed="move"; };
      c.ondragend = () => c.classList.remove("drag");
      c.onclick = e => { if(!e.target.closest("[data-excluir-lead]")) abreLead(c.dataset.id); }; });
    $$(".kcol").forEach(col => {
      col.ondragover = e => { e.preventDefault(); col.classList.add("drop"); };
      col.ondragleave = e => { if(!col.contains(e.relatedTarget)) col.classList.remove("drop"); };
      col.ondrop = async e => { e.preventDefault(); col.classList.remove("drop"); const st=col.dataset.st, l=S.map[arrastando]; if(!l||l.status===st) return;
        l.status=st; l.atualizado_em=Date.now()/1000; draw();
        try{ upsertLead(await api(`/api/leads/${encodeURIComponent(l.id)}`,{method:"PATCH",body:{status:st}})); toast(`${l.nome} → ${NOME_ST[st]}`); }catch(err){ toast(err.message); } };
    });
  };
  $("#kq").oninput = e => { FK.texto=e.target.value; ls.set("fk",FK); draw(); };
  $("#kb").onchange = e => { FK.busca=e.target.value; ls.set("fk",FK); draw(); };
  $("#kwa").onclick = e => { FK.wa=!FK.wa; ls.set("fk",FK); e.currentTarget.classList.toggle("on",FK.wa); draw(); };
  VIEWS.funil._draw = draw;
  draw();
};

