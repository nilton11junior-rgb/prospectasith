// Painel de qualificação e rascunhos. A ação de copiar só usa a área de transferência.
const Oportunidades = (() => {
  const estados = {
    concluida: "Auditado",
    executando: "Auditando",
    na_fila: "Na fila",
    nao_executada: "Aguardando auditoria",
    falhou: "Auditoria pendente de revisão"
  };
  const rotulo = (d, item) => d.prioridades[item.prioridade] || item.prioridade;

  function conteudo(item, dados){
    const grupo = dados.grupos[item.grupo];
    return `<p class="muted sm">${esc(grupo.nome)} · ${esc(estados[item.auditoria] || "")}
      ${item.auditado_em ? " · " + esc(fData(item.auditado_em)) : ""}</p>
      <p><strong>${esc(grupo.oferta)}</strong></p>
      <ul>${item.evidencias.map(texto => `<li>${esc(texto)}</li>`).join("")}</ul>
      <p class="sm"><strong>Próximo passo</strong> ${esc(item.acao)}</p>
      <p class="muted sm">${esc(item.canal || "Canal a confirmar")} · ${esc(item.campanha || "Sem campanha ativa correspondente")}</p>
      ${item.abordagem ? `<details class="op-rascunho">
        <summary>Primeira abordagem sugerida</summary><p class="op-texto">${esc(item.abordagem)}</p>
        <button type="button" class="btn sm" data-copiar-abordagem>${ic("copy")}Copiar rascunho</button>
      </details>` : ""}`;
  }

  function cartao(item, dados){
    return `<article class="card op-card">
      <div class="op-cab"><div><strong>${esc(item.nome)}</strong><div class="muted sm">${esc(item.cidade)}</div></div>
        <span class="pill nodot op-${esc(item.prioridade)}">${esc(rotulo(dados, item))}</span></div>
      ${conteudo(item, dados)}
      <button class="btn sm" type="button" data-op-ficha="${esc(item.id)}">Abrir ficha</button>
    </article>`;
  }

  async function mostrarFicha(id, destino){
    try{
      const d = await api(`/api/leads/${encodeURIComponent(id)}/oportunidade`);
      if(destino.isConnected && d.item){
        destino.innerHTML = `<div class="sec-t">Mini relatório comercial</div>
          <section class="card op-card"><strong>${esc(rotulo(d,d.item))}</strong>${conteudo(d.item,d)}</section>`;
      }
    }catch{
      if(destino.isConnected) destino.textContent = "Mini relatório indisponível nesta consulta.";
    }
  }

  function abrir(segmento){
    crumbs([["Prospecção", "#/buscas"], ["Oportunidades"]]);
    $("#page").innerHTML = `<div class="ph"><div><h1>Oportunidades</h1>
      <p>Escolha o lead pela evidência, pelo canal e pelo próximo passo da venda.</p></div>
      <div class="acts"><a class="btn" href="#/campanhas">Campanhas</a></div></div>
      <div id="opPainel">
        <div id="opResumo" class="op-resumo"></div><p id="opFila" class="muted sm"></p>
        <div class="op-filtros">
          <label>Oportunidade<select class="in" id="opGrupo"><option value="">Todos os grupos</option></select></label>
          <label>Próximo passo<select class="in" id="opPrioridade"><option value="">Todas as prioridades</option></select></label>
          <button type="button" class="btn" id="opAtualizar">${ic("refresh")}Atualizar</button>
        </div>
        <div id="opEscopo"></div>
        <p id="opErro" class="exclusao-erro" role="alert"></p>
        <div id="opItens" class="op-grid"><p class="muted">Carregando oportunidades…</p></div>
        <div id="opPaginacao" class="op-filtros"></div>
      </div>`;
    const root = $("#opPainel");
    const grupo = $("#opGrupo", root);
    const prioridade = $("#opPrioridade", root);
    let pagina = 1, timer, consulta = 0, assinatura = "";
    const preencher = (campo, opcoes, padrao) => {
      const anterior = campo.value;
      campo.innerHTML = `<option value="">${padrao}</option>` + opcoes.map(([k,n]) =>
        `<option value="${esc(k)}">${esc(n)}</option>`).join("");
      campo.value = anterior;
    };
    async function carregar(){
      clearTimeout(timer);
      if(!root.isConnected) return;
      const numero = ++consulta;
      const params = new URLSearchParams({grupo: grupo.value, prioridade: prioridade.value, pagina, segmento});
      try{
        const d = await api("/api/oportunidades?" + params);
        if(!root.isConnected || numero !== consulta) return;
        $("#opErro", root).textContent = "";
        pagina = d.pagina;
        const nova = JSON.stringify(d);
        if(nova === assinatura) return;
        assinatura = nova;
        preencher(grupo, Object.entries(d.grupos).map(([k,g])=>[k,`${g.nome} (${fN(g.total)})`]), "Todos os grupos");
        preencher(prioridade, Object.entries(d.prioridades), "Todas as prioridades");
        $("#opResumo", root).innerHTML = Object.entries(d.resumo).map(([k,n]) =>
          `<div class="card"><b>${fN(n)}</b><span>${esc(d.prioridades[k])}</span></div>`).join("");
        const a = d.auditorias;
        $("#opFila", root).textContent = `${fN(a.concluida)} auditados · ${fN(a.executando)} em coleta · ${fN(a.na_fila + a.nao_executada)} aguardando${a.falhou ? " · " + fN(a.falhou) + " para revisar" : ""}`;
        $("#opEscopo", root).innerHTML = segmento ? `<p class="sm">Público da campanha ${esc(d.campanha)} · <a href="#/oportunidades">Ver toda a base</a></p>` : "";
        $("#opItens", root).innerHTML = d.itens.length
          ? d.itens.map(item=>cartao(item,d)).join("")
          : '<p class="muted">Nenhuma oportunidade neste recorte. As empresas aparecem quando entram na base.</p>';
        $("#opPaginacao", root).innerHTML = `<button class="btn sm" id="opAnterior" ${pagina === 1 ? "disabled" : ""}>Anterior</button>
          <span class="muted sm">${fN(d.total)} leads · Página ${pagina} de ${d.paginas}</span>
          <button class="btn sm" id="opProxima" ${pagina === d.paginas ? "disabled" : ""}>Próxima</button>`;
        $("#opAnterior", root).onclick = () => {pagina--; carregar();};
        $("#opProxima", root).onclick = () => {pagina++; carregar();};
      }catch(e){
        if(root.isConnected && numero === consulta) $("#opErro", root).textContent = e.message;
      }finally{
        if(root.isConnected && numero === consulta) timer = setTimeout(carregar, 10000);
      }
    }
    grupo.onchange = prioridade.onchange = () => {pagina = 1; carregar();};
    $("#opAtualizar", root).onclick = carregar;
    carregar();
  }

  document.addEventListener("click", async e => {
    const ficha = e.target.closest("[data-op-ficha]");
    if(ficha) abreLead(ficha.dataset.opFicha);
    const copiar = e.target.closest("[data-copiar-abordagem]");
    if(!copiar) return;
    try{
      await navigator.clipboard.writeText($(".op-texto", copiar.closest("details")).textContent);
      toast("Rascunho copiado");
    }catch{toast("Selecione o texto do rascunho e copie.");}
  });
  return {abrir, mostrarFicha};
})();

VIEWS.oportunidades = Oportunidades.abrir;
