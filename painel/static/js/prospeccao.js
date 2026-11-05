// Prospecta: telas Início, Nova busca e Buscas. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ INÍCIO ═════════════
const tamanhoBusca = b => b.origem==='sithia_scraper'?'Scraper com mapa':(TAM[b.parametros.tamanho]?.[0]||'Importada');
VIEWS.inicio = async () => {
  crumbs([["Início"]]);
  const primeira = !$("#ini");
  if(primeira){
    const h = new Date().getHours(), saud = h<12?"Bom dia":h<18?"Boa tarde":"Boa noite";
    $("#page").innerHTML = `<div class="ph fade"><div><h1>${saud}!</h1><p>Sua central de prospecção, do mapa ao fechamento.</p></div>
      <div class="acts"><a class="btn" href="#/funil">${ic("kanban")}Abrir funil</a><a class="btn pri" href="#/scraper">${ic("pin")}Buscar no mapa</a></div></div>
      <div id="ini"><div class="empty">Carregando…</div></div>`;
  }
  let d; try{ d = await api("/api/inicio"); }catch{ return; }
  if(rota().v!=="inicio" || !$("#ini")) return;
  const ativas = S.buscas.filter(b=>b.estado==="rodando"||b.estado==="na_fila");
  const blocoAtivas = ativas.length ? `<div class="card ${primeira?"fade":""}" style="margin-bottom:16px"><div class="card-b">${ativas.map(b=>`
      <a href="#/buscas/${b.id}" style="color:inherit;text-decoration:none;display:block"><div class="row" style="margin-bottom:8px;flex-wrap:wrap"><span class="pill e-${b.estado}">${ESTADO[b.estado]}</span><b>${esc(b.parametros.nichos.join(", "))}</b><span class="muted sm">· ${esc(localB(b))}</span><span class="muted sm" style="margin-left:auto">${esc(b.etapa)}</span></div>${barraB(b)}</a>`).join('<div class="sep"></div>')}</div></div>` : "";
  if(!d.total){
    $("#ini").innerHTML = blocoAtivas + `<div class="card fade"><div class="empty" style="padding:70px 20px"><div class="ic">${ic("spark")}</div><b>Nenhum lead ainda</b>${ativas.length?"Sua primeira busca está rodando. Os leads aparecem aqui quando ela terminar.":"Faça sua primeira busca: escolha um nicho e uma cidade."}${ativas.length?"":`<div style="margin-top:16px"><a class="btn pri lg" href="#/nova">${ic("plus")}Fazer primeira busca</a></div>`}</div></div>`; return;
  }
  const st = d.por_status, trab = d.total - st.novo, F = primeira ? "fade" : "";
  const kpi = (lab, n, sub, icn, cor, bg) => `<div class="card kpi"><div class="ico" style="background:${bg};color:${cor}">${ic(icn)}</div><div class="l">${lab}</div><div class="n num">${n}</div><div class="s">${sub}</div></div>`;
  const etapas = ["contatado","respondeu","reuniao","fechado"];
  const acum = s => etapas.slice(etapas.indexOf(s)).reduce((a,k)=>a+st[k],0); // quantos chegaram pelo menos até esta etapa
  const hb = arr => arr.length ? `<div class="hb">${arr.map(([k,n])=>`<div class="hb-r"><div><div class="lab"><span>${esc(k)}</span></div><div class="bar"><i style="width:${n/arr[0][1]*100}%"></i></div></div><div class="num sm" style="text-align:right">${fN(n)}</div></div>`).join("")}</div>` : `<div class="muted sm">Sem dados.</div>`;
  const icEv = {whatsapp:"wa",status:"flag",nota:"note",ligacao:"phone",email:"mail"};
  $("#ini").innerHTML = blocoAtivas + `
    <div class="grid g4 ${F}">
      ${kpi("Leads na base", fN(d.total), `+${fN(d.novos_semana)} nesta semana`, "users", "var(--accent)", "var(--accent-soft)")}
      ${kpi("Com WhatsApp", fN(d.com_whatsapp), `${fPct(d.com_whatsapp,d.total)} da base`, "wa", "var(--wa)", "var(--green-soft)")}
      ${kpi("Em negociação", fN(st.contatado+st.respondeu+st.reuniao), `${fN(d.contatos_semana)} contatos nesta semana`, "trend", "var(--warn)", "var(--yellow-soft)")}
      ${kpi("Negócios fechados", fN(st.fechado), `conversão de ${fPct(st.fechado, trab)} dos trabalhados`, "check", "var(--green)", "var(--green-soft)")}
    </div>
    <div class="grid g-main" style="margin-top:16px">
      <div class="card ${F}"><div class="card-h"><h3>Funil de vendas</h3><div class="sp"></div><a class="sm" href="#/funil">Ver quadro →</a></div>
        <div class="card-b"><div class="fun">
          <div class="fun-r"><span>Leads na base</span><div class="fun-b"><i style="width:100%;background:var(--muted);opacity:.3"></i></div><b class="num" style="text-align:right">${fN(d.total)}</b></div>
          ${etapas.map(s=>`<div class="fun-r"><span>${NOME_ST[s]}</span><div class="fun-b"><i style="width:${acum(s)/d.total*100}%;background:${COR_ST[s]}"></i></div><div style="text-align:right"><b class="num">${fN(acum(s))}</b><div class="xs muted">${fPct(acum(s),d.total)}</div></div></div>`).join("")}
        </div>
        <div class="sep"></div>
        <div class="row sm" style="flex-wrap:wrap;gap:18px"><span class="muted">Ainda não contatados: <b style="color:var(--ink)">${fN(st.novo)}</b></span><span class="muted">Descartados: <b style="color:var(--ink)">${fN(st.descartado)}</b></span><span class="muted">Sem site: <b style="color:var(--warn)">${fN(d.sem_site)}</b></span><span class="muted">Com e-mail: <b style="color:var(--ink)">${fN(d.com_email)}</b></span></div>
        </div></div>
      <div class="card ${F}"><div class="card-h"><h3>Atividade recente</h3></div><div class="card-b">
        ${d.eventos.length?`<div class="tl">${d.eventos.map(e=>`<div class="tl-i"><div class="tl-d">${ic(icEv[e.tipo]||"note")}</div><div><div class="tl-t"><a href="#" data-lead="${esc(e.lead)}"><b>${esc(e.nome)}</b></a> — ${esc(rotuloEv(e))}</div><div class="tl-m">${fRel(e.t)}</div></div></div>`).join("")}</div>`
          :`<div class="empty" style="padding:24px 10px"><b>Nada por aqui ainda</b>Quando você chamar alguém no WhatsApp ou mudar um status, aparece aqui.</div>`}
      </div></div>
    </div>
    <div class="grid g3" style="margin-top:16px">
      <div class="card ${F}"><div class="card-h"><h3>Cidades</h3></div><div class="card-b">${hb(d.cidades)}</div></div>
      <div class="card ${F}"><div class="card-h"><h3>Bairros</h3></div><div class="card-b">${hb(d.bairros)}</div></div>
      <div class="card ${F}"><div class="card-h"><h3>Categorias</h3></div><div class="card-b">${hb(d.categorias)}</div></div>
    </div>`;
};
function rotuloEv(e){ return e.tipo==="whatsapp" ? "chamado no WhatsApp" : e.tipo==="ligacao" ? "ligação registrada" : e.tipo==="email" ? "e-mail enviado" : e.tipo==="status" ? e.txt.replace("Status: ","→ ") : e.txt; }
document.addEventListener("click", e => { const a = e.target.closest("[data-lead]"); if(a){ e.preventDefault(); abreLead(a.dataset.lead); } });

// ═════════════ NOVA BUSCA ═════════════
const SUGESTOES = ["clínicas odontológicas","clínicas de estética","academias","escritórios de advocacia","escritórios de contabilidade",
  "imobiliárias","pet shops","salões de beleza","barbearias","restaurantes","oficinas mecânicas","lojas de material de construção",
  "psicólogos","fisioterapia","autoescolas","escolas de idiomas","farmácias","óticas","clínicas veterinárias","nutricionistas",
  "ar condicionado","instalação de ar condicionado","engenharia de climatização","refrigeração"];
const NB = { tamanho: ls.get("nb_tam","padrao"), cidade: ls.get("ultimaCidade", null) };
VIEWS.nova = () => {
  crumbs([["Prospecção","#/buscas"],["Nova busca"]]);
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Nova busca</h1><p>Encontre empresas no Google Maps com telefone, WhatsApp, e-mail e redes sociais.</p></div></div>
  <div class="grid g-main fade">
    <form class="card" id="fNova" autocomplete="off"><div class="card-b" style="padding:22px 24px 24px">
      <label class="lbl" style="margin-top:0" for="nichos">O que você procura?</label>
      <input class="in" id="nichos" placeholder="ex.: clínicas odontológicas, ortodontistas" value="${esc(ls.get("nb_nichos",""))}">
      <div class="hint">Pode colocar mais de um, separados por vírgula. Escreva do jeito que um cliente buscaria no Google.</div>
      <div class="chips" id="sug" style="margin-top:10px">${SUGESTOES.map(s=>`<span class="chip" data-s="${esc(s)}">${esc(s)}</span>`).join("")}</div>
      <div class="grid g2" style="gap:14px">
        <div><label class="lbl" for="cidade">Cidade</label>
          <div class="ac"><input class="in" id="cidade" placeholder="Digite a cidade…" value="${NB.cidade?esc(NB.cidade.n+" - "+NB.cidade.uf):""}"><div class="ac-list" id="acList"></div></div></div>
        <div><label class="lbl" for="bairro">Bairro <span class="muted" style="font-weight:400">(opcional)</span></label>
          <input class="in" id="bairro" placeholder="ex.: Centro, Moema, Savassi"></div>
      </div>
      <label class="lbl">Tamanho da busca</label>
      <div class="tams" id="tams">${Object.entries(TAM).map(([k,[n,q,t]])=>`<div class="tam ${NB.tamanho===k?"on":""}" data-v="${k}"><b>${n}</b><div class="q num">${q}</div><small>empresas · ${t}</small></div>`).join("")}</div>
      <div id="tamAviso" style="margin-top:10px"></div>
      <div class="sep" style="margin:20px 0"></div>
      <label class="switch"><input type="checkbox" id="redes" checked> Procurar Instagram, Facebook e LinkedIn nos sites das empresas</label>
      <div style="display:flex;gap:10px;align-items:center;margin-top:22px;flex-wrap:wrap">
        <button class="btn pri lg" type="submit" id="bGo">${ic("search")}Buscar empresas</button>
        <span class="muted sm" id="filaInfo"></span>
      </div>
    </div></form>
    <div class="grid" style="align-content:start">
      <div class="card"><div class="card-h"><h3>Como funciona</h3></div><div class="card-b"><div class="steps">
        <div class="step"><div><b>Busca no Google Maps</b><span class="muted">Nome, telefone, endereço, nota e avaliações de cada empresa.</span></div></div>
        <div class="step"><div><b>Visita os sites</b><span class="muted">Procura e-mail, WhatsApp e redes sociais, inclusive nas páginas de contato.</span></div></div>
        <div class="step"><div><b>Organiza no seu CRM</b><span class="muted">Os leads entram na base sem duplicar. Status e anotações ficam guardados.</span></div></div>
      </div></div></div>
      <div class="note info">${ic("spark")}<span>As buscas rodam uma de cada vez, numa fila. Pode enfileirar várias e continuar trabalhando enquanto isso.</span></div>
    </div>
  </div>`;
  const marca = () => { const at = $("#nichos").value.split(",").map(x=>x.trim()); $$("#sug .chip").forEach(c=>c.classList.toggle("on", at.includes(c.dataset.s))); };
  marca();
  $("#nichos").oninput = () => { ls.set("nb_nichos", $("#nichos").value); marca(); };
  $("#sug").onclick = e => { const s=e.target.dataset.s; if(!s) return;
    const at=$("#nichos").value.split(",").map(x=>x.trim()).filter(Boolean), i=at.indexOf(s); i>=0?at.splice(i,1):at.push(s);
    $("#nichos").value = at.join(", "); ls.set("nb_nichos",$("#nichos").value); marca(); };
  const avisoTam = () => $("#tamAviso").innerHTML = NB.tamanho==="cidade" ? `<div class="note">${ic("flag")}<span>Busca grande: divide a cidade em 9 regiões e roda uma por vez. Se você fizer várias assim no mesmo dia, o Google pode bloquear seu IP por algumas horas.</span></div>` : "";
  avisoTam();
  $("#tams").onclick = e => { const t=e.target.closest(".tam"); if(!t) return; NB.tamanho=t.dataset.v; ls.set("nb_tam",NB.tamanho); $$(".tam").forEach(x=>x.classList.toggle("on",x===t)); avisoTam(); };
  const fila = S.buscas.filter(b=>b.estado==="rodando"||b.estado==="na_fila").length;
  $("#filaInfo").textContent = fila ? `${fila} busca${fila>1?"s":""} na frente na fila` : "";
  montaAutocomplete();
  $("#fNova").onsubmit = async e => {
    e.preventDefault();
    const c = NB.cidade && $("#cidade").value === `${NB.cidade.n} - ${NB.cidade.uf}` ? NB.cidade : (() => { const m=$("#cidade").value.match(/^\s*(.+?)\s*[-,/]\s*([A-Za-z]{2})\s*$/); return m?{n:m[1],uf:m[2].toUpperCase()}:null; })();
    if(!$("#nichos").value.trim()) return toast("Diga o que você procura (ex.: academias).");
    if(!c) return toast("Escolha a cidade na lista.");
    $("#bGo").disabled = true;
    try{ const b = await api("/api/buscas",{method:"POST",body:{nichos:$("#nichos").value,cidade:c.n,uf:c.uf,bairro:$("#bairro").value,tamanho:NB.tamanho,redes:$("#redes").checked}});
      await carregaBuscas(); toast("Busca adicionada à fila"); location.hash = `#/buscas/${b.id}`; }
    catch(err){ toast(err.message); $("#bGo").disabled=false; }
  };
};
async function montaAutocomplete(){
  if(!S.municipios.length){ try{ S.municipios = (await api("/api/municipios")).map(m=>({...m,k:semAc(m.n)})); }catch{} }
  let idx=-1; const inp=$("#cidade"), box=$("#acList"); if(!inp) return;
  const draw = () => { const q=semAc(inp.value.split(/\s+-\s+|,/)[0].trim()); if(!q){box.style.display="none";return;}
    const ini=[],meio=[]; for(const m of S.municipios){ if(m.k.startsWith(q)) ini.push(m); else if(m.k.includes(q)) meio.push(m); }
    const pop=(a,b)=>(b.cap-a.cap)||a.n.length-b.n.length; const res=ini.sort(pop).concat(meio.sort(pop)).slice(0,12); idx=-1;
    box.innerHTML = res.map((m,i)=>`<div data-i="${i}"><b style="font-weight:550">${esc(m.n)}</b><span>${m.uf} · DDD ${m.ddd}${m.cap?" · capital":""}</span></div>`).join("") || `<div style="cursor:default;color:var(--muted)">Nenhuma cidade encontrada</div>`;
    box._r=res; box.style.display="block"; };
  const pick = m => { NB.cidade=m; ls.set("ultimaCidade",m); inp.value=`${m.n} - ${m.uf}`; box.style.display="none"; };
  inp.oninput = draw;
  inp.onkeydown = e => { const it=$$("div[data-i]",box);
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){ e.preventDefault(); if(!it.length) return; idx=(idx+(e.key==="ArrowDown"?1:-1)+it.length)%it.length; it.forEach((x,i)=>x.classList.toggle("sel",i===idx)); it[idx].scrollIntoView({block:"nearest"}); }
    else if(e.key==="Enter"&&box.style.display==="block"&&it.length){ e.preventDefault(); pick(box._r[Math.max(idx,0)]); }
    else if(e.key==="Escape") box.style.display="none"; };
  box.onmousedown = e => { const d=e.target.closest("div[data-i]"); if(d) pick(box._r[+d.dataset.i]); };
}
document.addEventListener("click", e => { const box=$("#acList"); if(box && !e.target.closest(".ac")) box.style.display="none"; });

// ═════════════ BUSCAS ═════════════
const localB = b => `${b.parametros.bairro?b.parametros.bairro+", ":""}${b.parametros.cidade} - ${b.parametros.uf}`;
function barraB(b){
  if(b.estado!=="rodando") return b.estado==="na_fila" ? `<div class="bar"><i style="width:0"></i></div>` : "";
  const p=b.progresso; if(p&&p.total){ const v = p.fase==="maps" ? p.atual/p.total*.8 : .8+p.atual/p.total*.2; return `<div class="bar"><i style="width:${Math.round(v*100)}%"></i></div>`; }
  return `<div class="bar ind"><i></i></div>`;
}
VIEWS.buscas = arg => arg ? viewBusca(arg) : viewBuscas();
function viewBuscas(){
  crumbs([["Prospecção","#/buscas"],["Buscas"]]);
  const bs = S.buscas;
  $("#page").innerHTML = `<div class="ph"><div><h1>Buscas</h1><p>Histórico de todas as buscas, da mais recente para a mais antiga.</p></div><div class="acts"><a class="btn" href="#/lixeira">${ic("trash")}Lixeira${S.nLixeira?` (${S.nLixeira})`:""}</a><a class="btn pri" href="#/nova">${ic("plus")}Nova busca</a></div></div>
  <div class="card">${!bs.length?`<div class="empty" style="padding:60px 20px"><div class="ic">${ic("hist")}</div><b>Nenhuma busca ainda</b>Comece pela primeira.<div style="margin-top:14px"><a class="btn pri" href="#/nova">${ic("plus")}Nova busca</a></div></div>`:
  `<div class="twrap"><table class="t"><thead><tr><th>Busca</th><th>Local</th><th>Tamanho</th><th>Quando</th><th>Situação</th><th style="text-align:right">Empresas</th><th style="text-align:right">WhatsApp</th><th style="text-align:right">E-mail</th><th>Ações</th></tr></thead><tbody>
  ${bs.map(b=>`<tr data-b="${b.id}"><td><div class="lead-n">${esc(b.parametros.nichos.join(", "))}</div>${b.novos!=null&&b.estado==="concluida"?`<div class="lead-c">${fN(b.novos)} novos na base</div>`:""}</td>
    <td>${esc(localB(b))}</td><td class="muted">${tamanhoBusca(b)}</td><td class="muted sm">${fData(b.criado_em)}</td>
    <td style="min-width:170px"><span class="pill e-${b.estado}">${ESTADO[b.estado]}${b.posicao_fila>1?" · "+b.posicao_fila+"º":""}</span>${b.estado==="rodando"?`<div style="margin-top:6px">${barraB(b)}</div>`:""}${b.estado==="erro"?`<div class="xs" style="color:var(--err);margin-top:3px;max-width:240px">${esc(b.etapa)}</div>`:""}</td>
    <td class="num" style="text-align:right;font-weight:600">${b.estado==="concluida"?fN(b.total):b.parcial?`<span class="muted">${fN(b.parcial)}…</span>`:"—"}</td>
    <td class="num" style="text-align:right">${b.estado==="concluida"?`${fN(b.com_whatsapp)} <span class="muted xs">${fPct(b.com_whatsapp,b.total)}</span>`:"—"}</td>
    <td class="num" style="text-align:right">${b.estado==="concluida"?`${fN(b.com_email)} <span class="muted xs">${fPct(b.com_email,b.total)}</span>`:"—"}</td>
    <td><button class="btn danger sm" data-descartar="${esc(b.id)}" aria-label="Mandar busca para a lixeira" ${["rodando","na_fila"].includes(b.estado)?'disabled title="Cancele a busca antes de mandar para a lixeira"':'title="Mandar busca para a lixeira"'}>${ic("trash")}Lixeira</button></td></tr>`).join("")}
  </tbody></table></div>`}</div>`;
  $$("tr[data-b]").forEach(tr => tr.onclick = () => location.hash = `#/buscas/${tr.dataset.b}`);
  $$("[data-descartar]").forEach(bt => bt.onclick = e => {
    e.stopPropagation();
    const b = bs.find(b=>b.id===bt.dataset.descartar);
    if(b) descartarBusca(b.id, b.estado==="erro"?"Busca com erro":"Resultado ruim");
  });
}
async function descartarBusca(id, motivo){
  if(!confirma("del"+id,"Mandar esta busca para a lixeira? Leads novos que vieram só dela saem da base; os que você já trabalhou ficam. Dá para restaurar por 30 dias.")) return;
  try{
    await api(`/api/buscas/${encodeURIComponent(id)}/lixeira`,{method:"POST",body:{motivo}});
    await Promise.all([carregaBuscas(),carregaLeads(),carregaLixeira()]);
  }catch(e){ return toast(e.message); }
  toast("Busca na lixeira"); renderNav();
  if(location.hash==="#/buscas") render(); else location.hash="#/buscas";
}
function viewBusca(id){
  const b = S.buscas.find(x=>x.id===id);
  if(!b){ crumbs([["Buscas","#/buscas"],["Não encontrada"]]); $("#page").innerHTML = `<div class="card"><div class="empty"><b>Busca não encontrada</b><a href="#/buscas">Voltar para buscas</a></div></div>`; return; }
  crumbs([["Buscas","#/buscas"],[b.parametros.nichos.join(", ")]]);
  const rodando = b.estado==="rodando"||b.estado==="na_fila";
  const mesma = viewBusca.ult===id+b.estado && $("#tbl");  // só atualiza o progresso, sem recriar a tabela
  viewBusca.ult = id+b.estado;
  const progresso = rodando?`<div class="card" style="margin-bottom:16px" id="prog"><div class="card-b"><div class="row" style="margin-bottom:10px;flex-wrap:wrap"><b>${b.estado==="na_fila"?"Aguardando na fila":"Em andamento"}</b><span class="muted sm">${esc(b.etapa)}</span>${b.parcial?`<span class="sm" style="margin-left:auto"><b class="num">${fN(b.parcial)}</b> empresas encontradas até agora</span>`:""}</div>${barraB(b)}
      <div class="hint" style="margin-top:10px">Pode sair desta tela: a busca continua rodando e os leads aparecem sozinhos quando terminar.</div></div></div>`:"";
  if(mesma && rodando && $("#prog")){ $("#prog").outerHTML = progresso; return; }
  $("#page").innerHTML = `<div class="ph fade"><div><div class="row" style="margin-bottom:6px"><span class="pill e-${b.estado}">${ESTADO[b.estado]}</span><span class="muted sm">${tamanhoBusca(b)} · ${fData(b.criado_em)}</span></div><h1>${esc(b.parametros.nichos.join(", "))}</h1><p class="row">${ic("pin")} ${esc(localB(b))}</p></div>
    <div class="acts">${b.estado==="concluida"?`<button class="btn" id="bExpB">${ic("down")}Exportar</button>`:""}${rodando?`<button class="btn" id="bCanc">${ic("x")}Cancelar</button>`:`<button class="btn" id="bRep">${ic("refresh")}Rodar de novo</button>`}<select class="in" id="bMot" title="Por que está indo para a lixeira?" style="width:auto"><option>Resultado ruim</option><option>Nicho errado</option><option>Cidade errada</option><option>Duplicada</option><option>Outro</option></select><button class="btn danger" id="bDel" ${rodando?"disabled title=\"Cancele a busca antes\"":""}>${ic("trash")}Lixeira</button></div></div>
    ${progresso}
    ${b.estado==="erro"?`<div class="note err fade" style="margin-bottom:16px">${ic("flag")}<span><b>Deu erro:</b> ${esc(b.etapa)}</span></div>`:""}
    ${(b.avisos||[]).map(a=>`<div class="note" style="margin-bottom:10px">${esc(a)}</div>`).join("")}
    ${b.total?`<div class="grid g4 fade" style="margin-bottom:16px">
      <div class="card kpi"><div class="l">Empresas</div><div class="n num">${fN(b.total)}</div><div class="s">${fN(b.novos??b.total)} novas na base</div></div>
      <div class="card kpi"><div class="l">Com WhatsApp</div><div class="n num" style="color:var(--wa)">${fN(b.com_whatsapp)}</div><div class="s">${fPct(b.com_whatsapp,b.total)}</div></div>
      <div class="card kpi"><div class="l">Com e-mail</div><div class="n num">${fN(b.com_email)}</div><div class="s">${fPct(b.com_email,b.total)}</div></div>
      <div class="card kpi"><div class="l">Sem site</div><div class="n num" style="color:var(--warn)">${fN(b.sem_site)}</div><div class="s">oportunidade para quem vende site</div></div></div>
      <div class="card fade" id="tbl"></div>`:""}`;
  $("#bCanc") && ($("#bCanc").onclick = async()=>{ await api(`/api/buscas/${id}/cancelar`,{method:"POST"}); await carregaBuscas(); render(); });
  if(b.origem==='sithia_scraper' && $("#bRep")){
    $("#bRep").textContent='Abrir no mapa';$("#bRep").onclick=()=>location.hash=`#/scraper/${encodeURIComponent(b.scraper_job_id)}`;
  }else $("#bRep") && ($("#bRep").onclick = async()=>{ if(!confirma("rep"+id,"Rodar esta busca de novo? Leads novos entram na base; status e anotações dos atuais são mantidos.")) return; await api(`/api/buscas/${id}/repetir`,{method:"POST"}); await carregaBuscas(); render(); });
  $("#bDel").onclick = ()=>descartarBusca(id, $("#bMot").value);
  if($("#tbl")) api(`/api/buscas/${id}`).then(d => { const ids=new Set(d.lead_ids); const fonte = () => S.leads.filter(l=>ids.has(l.id));
    $("#bExpB") && ($("#bExpB").onclick = () => exportaCsv(fonte(), semAc(b.parametros.nichos[0]).replace(/\W+/g,"-")+"_"+semAc(b.parametros.cidade).replace(/\W+/g,"-")));
    tabelaLeads($("#tbl"), fonte, "b_"+id); });
}



// ═════════════ LIXEIRA (buscas descartadas) ═════════════
async function carregaLixeira(){ try{ S.nLixeira = (await api("/api/lixeira")).length; }catch{} }
VIEWS.lixeira = async () => {
  crumbs([["Prospecção","#/buscas"],["Lixeira"]]);
  let ls = []; try{ ls = await api("/api/lixeira"); }catch(e){ return toast(e.message); }
  S.nLixeira = ls.length; renderNav();
  if(rota().v!=="lixeira") return;
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Lixeira</h1><p>Buscas descartadas. Ficam aqui por 30 dias e depois são apagadas. Restaurar traz de volta a busca e os leads que saíram com ela.</p></div>
    <div class="acts">${ls.length?`<button class="btn danger" id="lxVazia">${ic("trash")}Esvaziar lixeira</button>`:""}</div></div>
    <div class="card fade">${!ls.length?`<div class="empty" style="padding:60px 20px"><div class="ic">${ic("trash")}</div><b>Lixeira vazia</b>As buscas que você descartar aparecem aqui.</div>`:
    `<div class="twrap"><table class="t"><thead><tr><th>Busca</th><th style="text-align:right">Empresas</th><th style="text-align:right">Saem da base</th><th></th></tr></thead><tbody>
    ${ls.map(b=>`<tr><td><div class="lead-n">${esc(b.parametros.nichos.join(", "))}</div><div class="lead-c">${esc(localB(b))} · ${esc(b.lixeira_motivo||"sem motivo")}</div><div class="lead-c">${fData(b.lixeira_em)} · apaga em ${b.dias_restantes} dia${b.dias_restantes===1?"":"s"}</div></td>
      <td class="num" style="text-align:right">${fN(b.total)}</td><td class="num" style="text-align:right">${fN(b.leads_guardados)}</td>
      <td style="white-space:nowrap;text-align:right"><button class="btn sm" data-rest="${b.id}" title="Restaurar">${ic("refresh")}Restaurar</button> <button class="btn sm danger" data-del="${b.id}" title="Excluir de vez">${ic("trash")}</button></td></tr>`).join("")}
    </tbody></table></div>`}</div>
    ${ls.length?`<div class="hint fade" style="margin-top:10px">“Saem da base” = leads novos que vieram só dessa busca e que você nunca trabalhou. Quem você já contatou ou anotou fica na base mesmo se a busca for excluída.</div>`:""}`;
  $$("[data-rest]").forEach(b => b.onclick = async () => { try{ await api(`/api/buscas/${b.dataset.rest}/restaurar`,{method:"POST",body:{}}); }catch(e){ return toast(e.message); }
    await Promise.all([carregaBuscas(),carregaLeads()]); toast("Busca restaurada"); VIEWS.lixeira(); });
  $$("[data-del]").forEach(b => b.onclick = async () => { if(!confirma("lxdel"+b.dataset.del,"Excluir de vez? Não dá para desfazer.")) return;
    try{ await api(`/api/buscas/${b.dataset.del}`,{method:"DELETE"}); }catch(e){ return toast(e.message); }
    await carregaLeads(); toast("Busca excluída"); VIEWS.lixeira(); });
  $("#lxVazia") && ($("#lxVazia").onclick = async () => { if(!confirma("lxvazia",`Apagar de vez as ${ls.length} buscas da lixeira? Não dá para desfazer.`)) return;
    const r = await api("/api/lixeira/esvaziar",{method:"POST",body:{}}); await carregaLeads(); toast(`${r.apagadas} buscas apagadas`); VIEWS.lixeira(); });
};
