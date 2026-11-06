// Prospecta: Mensagens, Configurações e exportação. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ MENSAGENS ═════════════
let tplEd = null;
VIEWS.mensagens = async () => {
  crumbs([["Ajustes"],["Mensagens"]]);
  if(!S.config) try{ S.config = await api("/api/config"); }catch{ return; }
  const C = JSON.parse(JSON.stringify(S.config));
  if(!tplEd || !C.templates.find(t=>t.id===tplEd)) tplEd = C.templates[0]?.id;
  const ex = S.leads.find(l=>l.whatsapp) || {nome:"Clínica Sorriso", cidade:"Florianópolis", bairro:"Centro", categoria:"Dentista"};
  const draw = () => {
    const t = C.templates.find(x=>x.id===tplEd);
    $("#page").innerHTML = `<div class="ph"><div><h1>Mensagens</h1><p>Modelos prontos para o WhatsApp. Na ficha do lead, você escolhe qual usar e a mensagem já vai escrita.</p></div>
      <div class="acts"><button class="btn" id="tNovo">${ic("plus")}Novo modelo</button><button class="btn pri" id="tSalva">${ic("check")}Salvar alterações</button></div></div>
      <div class="grid" style="grid-template-columns:${innerWidth<800?"1fr":"minmax(0,300px) minmax(0,1fr)"};align-items:start">
        <div class="card tpl-list" style="overflow:hidden">${C.templates.map(x=>`<div class="it ${x.id===tplEd?"on":""}" data-t="${esc(x.id)}"><div class="row"><b>${esc(x.nome)}</b>${C.padrao===x.id?'<span class="pill s-fechado nodot" style="margin-left:auto">padrão</span>':""}</div><p>${esc(x.texto)}</p></div>`).join("")}</div>
        ${t?`<div class="card"><div class="card-b" style="padding:20px 22px">
          <label class="lbl" style="margin-top:0">Nome do modelo</label><input class="in" id="tNome" value="${esc(t.nome)}">
          <label class="lbl">Mensagem</label><textarea class="in" id="tTxt" rows="6">${esc(t.texto)}</textarea>
          <div class="chips" style="margin-top:8px">${["nome","cidade","bairro","categoria"].map(v=>`<span class="chip" data-var="${v}">+ {${v}}</span>`).join("")}</div>
          <div class="hint">Clique numa variável para inserir. Ela é trocada pelos dados de cada empresa.</div>
          <label class="lbl">Prévia (com ${esc(ex.nome)})</label>
          <div class="wa-prev"><div class="bubble" id="tPrev"></div></div>
          <div class="sep"></div>
          <div class="row" style="flex-wrap:wrap;gap:14px">
            <label class="switch"><input type="checkbox" id="tPad" ${C.padrao===t.id?"checked":""}> Usar como padrão</label>
            <button class="btn sm danger" id="tDel" style="margin-left:auto" ${C.templates.length<2?"disabled":""}>${ic("trash")}Excluir modelo</button>
          </div>
        </div></div>`:""}
      </div>
      <div class="card" style="margin-top:16px"><div class="card-b"><label class="switch"><input type="checkbox" id="tAuto" ${C.auto_contatado?"checked":""}> Quando eu clicar em WhatsApp, Ligar ou E-mail, mover o lead de “Novo” para “Contatado” automaticamente</label></div></div>`;
    const prev = () => { $("#tPrev") && ($("#tPrev").innerHTML = esc(preencheTpl($("#tTxt").value, ex)) + `<small>${new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})} ✓✓</small>`); };
    prev();
    $$(".tpl-list .it").forEach(it => it.onclick = () => { tplEd = it.dataset.t; draw(); });
    if(t){
      $("#tNome").oninput = e => t.nome = e.target.value;
      $("#tTxt").oninput = e => { t.texto = e.target.value; prev(); };
      $$("[data-var]").forEach(c => c.onclick = () => { const ta=$("#tTxt"), s=ta.selectionStart, v=`{${c.dataset.var}}`; ta.value=ta.value.slice(0,s)+v+ta.value.slice(ta.selectionEnd); t.texto=ta.value; ta.focus(); ta.setSelectionRange(s+v.length,s+v.length); prev(); });
      $("#tPad").onchange = e => { if(e.target.checked) C.padrao=t.id; };
      $("#tDel").onclick = () => { if(!confirma("tdel"+t.id,"Excluir este modelo?")) return; C.templates = C.templates.filter(x=>x.id!==t.id); if(C.padrao===t.id) C.padrao=C.templates[0].id; tplEd=C.templates[0].id; draw(); };
    }
    $("#tAuto").onchange = e => C.auto_contatado = e.target.checked;
    $("#tNovo").onclick = () => { const id = Math.random().toString(36).slice(2,10); C.templates.push({id, nome:"Novo modelo", texto:"Olá! Vi a {nome} no Google Maps…"}); tplEd=id; draw(); $("#tNome").select(); };
    $("#tSalva").onclick = async () => { try{ S.config = await api("/api/config",{method:"PUT",body:C}); toast("Mensagens salvas"); }catch(err){ toast(err.message); } };
  };
  draw();
};

// ═════════════ CONFIGURAÇÕES ═════════════
VIEWS.config = async () => {
  crumbs([["Ajustes"],["Configurações"]]);
  let st = {motor:false}, scraperOn=false;
  await Promise.all([api("/api/status").then(x=>st=x).catch(()=>{}),api("/api/scraper/jobs").then(()=>scraperOn=true).catch(()=>{})]);
  if(rota().v!=="config") return;
  $("#page").innerHTML = `<div class="ph fade"><div><h1>Configurações</h1><p>Motor de busca, seus dados e backup.</p></div></div>
  <div class="grid g2 fade">
    <div class="card"><div class="card-h"><h3>SITH.IA Scraper</h3></div><div class="card-b">
      <div class="row"><span class="dot ${scraperOn?'ok':'off'}"></span><b>${scraperOn?'Conectado à central':'Scraper desligado'}</b></div>
      <p class="muted sm">Mapa, filtros e importação para a sua base de leads. O motor adicional usa a porta 8081.</p>
      <a class="btn pri sm" href="#/scraper">${ic('pin')}Abrir mapa de prospecção</a>
      ${st.automacoes_pausadas?'<div class="note" style="margin-top:14px">Envios automáticos pausados nesta abertura. Campanhas e configurações foram mantidas. Para retomar as rotinas configuradas, reabra o iniciador com --automacoes.</div>':''}
    </div></div>
    <div class="card"><div class="card-h"><h3>Motor de busca</h3></div><div class="card-b">
      <div class="row" style="margin-bottom:12px"><span class="dot ${st.motor?"ok":"off"}"></span><b>${st.motor?"Ligado e respondendo":"Desligado"}</b></div>
      ${st.motor?`<p class="muted sm" style="margin:0">O motor roda em <code>localhost:8080</code> e só aceita conexões do seu computador.</p>`:
      `<div class="note err">${ic("flag")}<span>Feche e abra de novo o sistema com dois cliques no <b>Prospeccao.cmd</b> (na pasta do projeto).</span></div>`}
      <div class="sep"></div>
      <div class="sm"><b>Para abrir o sistema no dia a dia:</b> dois cliques em <code>Prospecta SITH.IA.cmd</code>. Ele liga os motores, o painel e prepara o WhatsApp em segundo plano.</div>
      <div class="row" style="margin-top:12px"><button class="btn sm" id="cSair">${ic("out")}Sair do painel</button></div>
    </div></div>
    <div class="card"><div class="card-h"><h3>Seus dados</h3></div><div class="card-b">
      <div class="grid g3" style="gap:10px;margin-bottom:14px">
        <div><div class="xs muted">Leads</div><div style="font-size:20px;font-weight:700" class="num">${fN(S.leads.length)}</div></div>
        <div><div class="xs muted">Buscas</div><div style="font-size:20px;font-weight:700" class="num">${fN(S.buscas.length)}</div></div>
        <div><div class="xs muted">Trabalhados</div><div style="font-size:20px;font-weight:700" class="num">${fN(S.leads.filter(l=>l.status!=="novo").length)}</div></div>
      </div>
      <p class="muted sm" style="margin:0 0 12px">Tudo fica salvo só no seu computador, na pasta <code>painel/dados/</code>. Nada vai para a nuvem.</p>
      <button class="btn" id="cExp">${ic("down")}Baixar base completa (Excel)</button>
    </div></div>
    <div class="card"><div class="card-h"><h3>Boas práticas</h3></div><div class="card-b sm">
      <div class="steps">
        <div class="step"><div><b>Não exagere nas buscas grandes</b><span class="muted">Muitas buscas “Cidade inteira” seguidas podem fazer o Google bloquear seu IP por algumas horas.</span></div></div>
        <div class="step"><div><b>Personalize a abordagem</b><span class="muted">Mensagens com o nome da empresa e o bairro têm muito mais resposta do que texto genérico.</span></div></div>
        <div class="step"><div><b>Respeite a LGPD</b><span class="muted">Use os dados só para contato comercial com empresas, marque como “Descartado” quem pedir para não ser contatado e não revenda a base.</span></div></div>
      </div></div></div>
    <div class="card"><div class="card-h"><h3>Sobre</h3></div><div class="card-b sm muted">
      Painel feito sobre o <b style="color:var(--ink)">Google Maps Scraper Kit</b>, com o motor de código aberto <code>gosom/google-maps-scraper</code> (licença MIT). Lista de municípios com códigos e coordenadas do IBGE.
    </div></div>
  </div>`;
  $("#cExp").onclick = () => exportaCsv(S.leads, "base-completa");
  $("#cSair").onclick = sair;
};

// ═════════════ exportação ═════════════
function exportaCsv(rows, nome){
  if(!rows.length) return toast("Nada para exportar.");
  const cols = [["Empresa","nome"],["Categoria","categoria"],["Telefone","telefone"],["Tipo de telefone","tel_tipo"],
    ["WhatsApp",l=>l.whatsapp?fTel(l.whatsapp):""],["Link WhatsApp",l=>l.whatsapp?`https://wa.me/${l.whatsapp}`:""],
    ["E-mail","email"],["Site","site"],["Instagram","instagram"],["Facebook","facebook"],["LinkedIn","linkedin"],
    ["Endereço","endereco"],["Bairro","bairro"],["Cidade","cidade"],["UF","uf"],["CEP","cep"],
    ["Nota",l=>l.nota?String(l.nota).replace(".",","):""],["Avaliações","avaliacoes"],["Google Maps","maps"],
    ["Status",l=>NOME_ST[l.status]||l.status],["Anotações","obs"]];
  const cel = v => { v=String(v??""); return /[;"\n\r]/.test(v) ? `"${v.replace(/"/g,'""')}"` : v; };
  // separador ; + BOM: abre certinho no Excel em português
  const csv = "﻿" + [cols.map(c=>c[0]).join(";"), ...rows.map(l=>cols.map(([,k])=>cel(typeof k==="function"?k(l):l[k])).join(";"))].join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  a.download = `sithia_${nome}_${new Date().toISOString().slice(0,10)}.csv`; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000); toast(`${fN(rows.length)} leads exportados`);
}
async function copiaWhats(rows){
  const nums=[...new Set(rows.filter(l=>l.whatsapp).map(l=>l.whatsapp))];
  try{ await navigator.clipboard.writeText(nums.join("\n")); toast(`${fN(nums.length)} números copiados`); }catch{ toast("Não consegui copiar"); }
}

