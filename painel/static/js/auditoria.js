// Relatório por empresa. Verificações manuais ficam separadas da coleta de tags.
const AuditoriaDigital = (() => {
  const etapas = {
    nao_executada: "Pronta para iniciar",
    na_fila: "Na fila",
    executando: "Coletando dados públicos…",
    concluida: "Coleta concluída",
    falhou: "A coleta falhou. Você pode tentar novamente."
  };
  const link = (url, rotulo) => {
    const href = urlSegura(url);
    return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(rotulo)} ↗</a>` : "";
  };
  const secao = (titulo, corpo) => `<section class="audit-card"><h3>${titulo}</h3>${corpo}</section>`;
  const par = (nome, valor) => `<dt>${esc(nome)}</dt><dd>${esc(valor || "—")}</dd>`;

  function cadastro(c){
    const estados = {
      nao_encontrado: "CNPJ não localizado nas páginas visitadas.",
      ambiguo: "O site publica mais de um CNPJ. Confira qual pertence à empresa.",
      revisar: "O cadastro encontrado diverge do nome ou da localidade do lead. Confira antes de associar.",
      indisponivel: "A BrasilAPI não respondeu à consulta.",
      sem_cadastro: "A BrasilAPI não retornou um cadastro para esse número."
    };
    const candidatos = (c.candidatos || []).map(x => `<li>
      <button type="button" class="btn sm" data-audit-cnpj="${esc(x.cnpj)}">${esc(x.cnpj)}</button>
      ${esc([x.razao_social, x.cidade, x.uf].filter(Boolean).join(" · "))}
      ${link(x.publicado_em, "Onde apareceu")}
    </li>`).join("");
    if(!c.cnpj) return secao("CNPJ e sócios", `<p>${esc(estados[c.estado] || "")}</p>${candidatos ? `<ul>${candidatos}</ul>` : ""}`);
    const socios = c.socios.map(s => `<li><strong>${esc(s.nome)}</strong> ${esc(s.qualificacao)}
      ${s.contatos.length ? s.contatos.map(p => `<div>${esc([p.telefone, p.email].filter(Boolean).join(" · "))} ${link(p.fonte, "Contato publicado")}</div>`).join("")
                          : '<div class="muted">Contato profissional direto não localizado.</div>'}
    </li>`).join("");
    return secao("CNPJ e sócios", `<dl>${par("CNPJ", c.cnpj)}${par("Razão social", c.razao_social)}
      ${par("Localidade", [c.cidade, c.uf].filter(Boolean).join(" / "))}${par("Situação", c.situacao)}</dl>
      <p>${link(c.fonte, "Cadastro na BrasilAPI")} · ${c.estado === "informado" ? "CNPJ informado na auditoria" : "Cadastro compatível com o lead"}
      ${c.estado === "informado" && !c.compativel ? " · Nome ou localidade diverge do lead" : ""}</p>
      ${socios ? `<ul>${socios}</ul>` : '<p class="muted">A consulta não retornou sócios.</p>'}
      <p class="muted">Contato do cadastro da empresa: ${esc([c.telefone, c.email].filter(Boolean).join(" · ") || "não publicado")}</p>`);
  }

  function site(s, v){
    if(s.estado === "sem_site") return secao("Site e velocidade", "<p>O lead não tem site cadastrado.</p>");
    if(s.estado === "somente_perfil") return secao("Site e velocidade", `<p>O endereço cadastrado é um perfil ou agregador de links. ${link(s.url, "Abrir endereço")}</p>`);
    if(s.estado === "indisponivel") return secao("Site e velocidade", `<p>${esc(s.motivo)}</p>`);
    const estrutura = s.paginas ? `<dl>${par("Título", s.titulo)}${par("Descrição", s.descricao)}
      ${par("HTTPS", s.https ? "Sim" : "Site entregue por HTTP")}
      ${par("Viewport móvel", s.responsivo ? "Declarado" : "Não declarado")}
      ${par("Cabeçalhos H1", String(s.h1))}${par("Imagens sem alt", s.imagens_sem_alt + " de " + s.imagens)}
      ${par("Indexação", s.noindex ? "Meta noindex presente" : "Meta noindex não detectada")}</dl>
      <p class="muted">${s.paginas.length} página(s) HTML lida(s)${s.truncado ? " · leitura parcial da página inicial" : ""}.</p>` : "";
    const velocidade = v.estado === "medido"
      ? `<p><strong>Lighthouse móvel ${v.nota}/100</strong> · ${esc(Object.entries(v.metricas).map(([k, n]) => k + " " + n).join(" · "))}</p>`
      : `<p class="muted">${v.estado === "sem_chave" ? "Lighthouse automático disponível com chave PageSpeed configurada." : "Medição Lighthouse indisponível nesta coleta."}</p>`;
    const resposta = s.ttfb_ms > 1800 ? "Resposta inicial demorada" :
      s.ttfb_ms > 800 ? "Resposta inicial acima da referência" : "Resposta inicial rápida";
    return secao("Site e velocidade", `<p>${link(s.url, "Página visitada")} · HTTP ${s.status}</p>
      ${s.estado === "respondendo" ? `<p><strong>${resposta} nesta coleta</strong></p>` : ""}
      <p><strong>${fN(s.ttfb_ms)} ms</strong> até os cabeçalhos da resposta · ${fN(s.ms)} ms na consulta HTML</p>
      <p class="muted">Medição desta conexão. A velocidade de renderização é medida pelo Lighthouse.</p>
      ${velocidade}${link(v.url, "Abrir PageSpeed Insights")}${estrutura}`);
  }

  function relatorio(r){
    if(!r) return '<p class="muted">Execute a auditoria para coletar os dados públicos da empresa.</p>';
    const wa = r.whatsapp, ig = r.instagram;
    const estadosWa = {
      nao_detectado: "Link de WhatsApp não detectado no HTML visitado.",
      sem_numero: "Link publicado sem número válido para contato direto.",
      erro_http: "O link retornou erro HTTP " + (wa.status || "") + ".",
      numero_invalido: "O WhatsApp sinalizou um número inválido.",
      link_responde: "O link respondeu. A existência da conta e a entrega de mensagens ficam sem validação.",
      inconclusivo: "Link identificado. O WhatsApp limitou ou não respondeu ao teste."
    };
    const contato = [
      ...r.contatos.telefones.map(x => [x.valor, x.fonte]),
      ...r.contatos.emails.map(x => [x.valor, x.fonte])
    ].map(([valor, fonte]) => `<li>${esc(valor)} · ${link(fonte, "Fonte")}</li>`).join("");
    const tags = r.tags.map(t => `<li><strong>${esc(t.nome)}</strong> · ${esc(t.evidencia)} · ${link(t.fonte, "Página")}</li>`).join("");
    return `<p class="muted sm">Coleta em ${fData(r.atualizado_em)}</p><div class="audit-grid">
      ${cadastro(r.cadastro)}${site(r.site, r.velocidade)}
      ${secao("Contatos e WhatsApp", `<p>${esc(estadosWa[wa.estado] || "")} ${link(wa.url, "Abrir link")} ${link(wa.fonte, "Página do botão")}</p>
        ${contato ? `<ul>${contato}</ul>` : '<p class="muted">Nenhum telefone ou e-mail publicado nos links visitados.</p>'}`)}
      ${secao("Instagram", `<p>${link(ig.url, "Abrir perfil")}</p>${ig.estado === "perfil_publico"
        ? `<p><strong>${esc(ig.titulo)}</strong></p><p>${esc(ig.descricao)}</p>`
        : `<p class="muted">${ig.url ? "Perfil identificado. A leitura pública foi limitada." : "Perfil não localizado."}</p>`}`)}
      ${secao("Tags detectadas no site", tags ? `<ul>${tags}</ul><p class="muted">Tags indicam instrumentação e podem existir sem campanhas ativas.</p>`
        : '<p class="muted">Nenhuma tag reconhecida no HTML consultado. Tags carregadas depois do consentimento ou via JavaScript podem escapar desta leitura.</p>')}
    </div>`;
  }

  function anuncios(d){
    return `<div class="audit-grid">${[["google","Google Ads"],["meta","Meta Ads"]].map(([plataforma,nome]) => {
      const prova = d.anuncios[plataforma] || {};
      const opcoes = [["pendente","Pendente"],["encontrado","Anúncio encontrado"],["nao_localizado","Não localizado na pesquisa"]];
      return secao(nome, `<p>${link(d.bibliotecas[plataforma], "Consultar biblioteca oficial · Brasil")}</p>
        <p class="muted">${prova.verificado_em ? "Verificação manual em " + fData(prova.verificado_em) : "Confirmação pela biblioteca ainda pendente."}</p>
        <form class="audit-evidencia" data-plataforma="${plataforma}">
          <label>Resultado<select name="estado" class="in">${opcoes.map(([id,n]) =>
            `<option value="${id}" ${(prova.estado || "pendente") === id ? "selected" : ""}>${n}</option>`).join("")}</select></label>
          <label>Link oficial da evidência<input class="in" name="url" type="url" value="${esc(prova.url)}" maxlength="1600"></label>
          <button class="btn sm" type="submit">Salvar verificação</button>
        </form>`);
    }).join("")}</div>`;
  }

  async function abrir(id){
    const lead = S.map[id] || (typeof leadAberto !== "undefined" && leadAberto?.id === id ? leadAberto : null);
    if(!lead || $("dialog[open]")) return;
    const dialog = document.createElement("dialog");
    dialog.className = "exclusao-dialog audit-dialog";
    dialog.setAttribute("aria-labelledby", "auditTitulo");
    dialog.innerHTML = `<div class="exclusao-body">
      <div class="audit-top"><div><h2 id="auditTitulo">Auditoria digital</h2><strong>${esc(lead.nome)}</strong></div>
        <button class="btn sm" id="auditFechar" type="button" autofocus>Fechar</button></div>
      <form id="auditColeta" class="audit-coleta">
        <label>CNPJ, se você souber<input class="in" id="auditCnpj" maxlength="22" placeholder="00.000.000/0000-00"></label>
        <button class="btn pri" id="auditRodar" type="submit" disabled>Executar auditoria</button>
      </form>
      <p id="auditStatus" role="status">Carregando auditoria…</p>
      <p id="auditErro" class="exclusao-erro" role="alert"></p>
      <div id="auditRelatorio"></div>
      <h3>Verificação de anúncios</h3><div id="auditAnuncios"></div>
    </div>`;
    document.body.append(dialog);
    dialog.showModal();
    const caminho = `/api/leads/${encodeURIComponent(id)}/auditoria`;
    const campo = $("#auditCnpj", dialog), status = $("#auditStatus", dialog);
    const erro = $("#auditErro", dialog), rodar = $("#auditRodar", dialog);
    const regiao = $("#auditAnuncios", dialog);
    let timer, ultimaColeta, iniciou = false;
    $("#auditFechar", dialog).onclick = () => dialog.close();
    dialog.addEventListener("close", () => {clearTimeout(timer); dialog.remove();});

    function atualizar(d, atualizarAnuncios = false){
      if(!dialog.open) return;
      if(!iniciou){campo.value = d.cnpj_informado || ""; iniciou = true;}
      status.textContent = etapas[d.estado] || d.estado;
      const ocupada = ["na_fila", "executando"].includes(d.estado);
      rodar.disabled = ocupada;
      const coleta = d.relatorio?.atualizado_em || 0;
      if(coleta !== ultimaColeta){
        $("#auditRelatorio", dialog).innerHTML = relatorio(d.relatorio);
        ultimaColeta = coleta;
      }
      if(atualizarAnuncios || !regiao.innerHTML) regiao.innerHTML = anuncios(d);
      clearTimeout(timer);
      if(ocupada) timer = setTimeout(carregar, 2500);
    }
    async function carregar(){
      try{atualizar(await api(caminho));}
      catch(e){erro.textContent = e.message; rodar.disabled = false;}
    }
    $("#auditColeta", dialog).onsubmit = async e => {
      e.preventDefault();
      rodar.disabled = true;
      erro.textContent = "";
      try{atualizar(await api(caminho, {method:"POST", body:{cnpj:campo.value.trim()}}));}
      catch(e){erro.textContent = e.message; rodar.disabled = false;}
    };
    dialog.addEventListener("click", e => {
      const cnpj = e.target.closest("[data-audit-cnpj]");
      if(cnpj){campo.value = cnpj.dataset.auditCnpj; campo.focus();}
    });
    regiao.addEventListener("submit", async e => {
      e.preventDefault();
      const form = e.target, botao = $("button", form), dados = new FormData(form);
      botao.disabled = true;
      erro.textContent = "";
      try{
        const r = await api(caminho + "/anuncios", {method:"POST", body:{
          plataforma:form.dataset.plataforma, estado:dados.get("estado"), url:dados.get("url").trim()}});
        atualizar(r, true);
        toast("Verificação de anúncios salva");
      }catch(e){erro.textContent = e.message; botao.disabled = false;}
    });
    carregar();
  }

  async function enfileirarBusca(id, botao){
    botao.disabled = true;
    try{
      const r = await api(`/api/buscas/${encodeURIComponent(id)}/auditoria`, {method:"POST", body:{}});
      const partes = [`${fN(r.na_fila)} na fila`];
      if(r.ja_auditadas) partes.push(`${fN(r.ja_auditadas)} já auditadas`);
      if(r.ja_em_andamento) partes.push(`${fN(r.ja_em_andamento)} em andamento`);
      if(r.sem_vaga) partes.push(`${fN(r.sem_vaga)} aguardam vaga. Clique novamente mais tarde.`);
      toast(partes.join(" · "));
    }catch(e){toast(e.message);}
    finally{botao.disabled = false;}
  }

  document.addEventListener("click", e => {
    const botao = e.target.closest("[data-auditar-lead]");
    if(botao) abrir(botao.dataset.auditarLead);
  });
  return {enfileirarBusca};
})();

function botaoAuditarLead(id){
  return `<button class="btn sm busca-excluir" type="button" data-auditar-lead="${esc(id)}">${ic("search")}Auditoria digital</button>`;
}
