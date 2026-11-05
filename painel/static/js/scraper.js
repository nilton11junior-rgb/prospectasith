// Busca com mapa -> importação explícita -> fluxo comercial existente do Prospecta.
const ScraperUI = (() => {
  const etapas={pending:'Na fila',working:'Buscando',ok:'Concluída',failed:'Falhou'};
  const estado={jobs:[],selecionada:ls.get('sithScraperJob',''),empresas:[],filtro:'todas',texto:'',pagina:0,conectado:false};
  let epoca=0,timer=null,carregando=false,criando=false,importando=false;
  const ativa = token => token===epoca && rota().v==='scraper' && !!$('#scRoot');
  const jobAtual = () => estado.jobs.find(j=>j.id===estado.selecionada);
  function fechar(){ epoca++;clearInterval(timer);timer=null;carregando=false;ScraperMapa.fechar(); }
  function tipoSite(site){
    if(!site) return 'nenhum';
    try { const host=new URL(urlSegura(site)).hostname.toLowerCase().replace(/^www\./,'');
      return ['instagram.com','facebook.com','linktr.ee','wa.me','whatsapp.com','tiktok.com'].some(d=>host===d||host.endsWith('.'+d))?'social':'site';
    }catch{return 'nenhum';}
  }
  function filtradas(){
    return estado.empresas.filter(e=>{
      const kind=tipoSite(e.site);
      return (!estado.texto || semAc(`${e.nome} ${e.bairro} ${e.cidade}`).includes(semAc(estado.texto))) &&
        (estado.filtro==='todas'||estado.filtro==='sem_site'&&kind==='nenhum'||estado.filtro==='social'&&kind==='social'||
         estado.filtro==='whatsapp'&&e.whatsapp||estado.filtro==='email'&&e.email);
    });
  }
  function mensagem(texto,erro=false){
    const el=$('#scNotice');if(!el)return;
    el.textContent=texto;el.className=erro?'sc-notice error':'sc-notice';
  }
  function atualizarResumo(){
    if(!$('#scRoot'))return;
    const job=jobAtual(),lista=filtradas(),total=estado.empresas.length;
    $('#scTotal').textContent=fN(total);
    $('#scWhats').textContent=fN(estado.empresas.filter(e=>e.whatsapp).length);
    $('#scSemSite').textContent=fN(estado.empresas.filter(e=>tipoSite(e.site)==='nenhum').length);
    $('#scEmails').textContent=fN(estado.empresas.filter(e=>e.email).length);
    $('#scJobState').textContent=job?(etapas[job.status]||'Estado desconhecido'):'Escolha uma busca';
    const bt=$('#scImport');
    bt.disabled=importando||!estado.conectado||!job||job.status!=='ok'||job.na_lixeira||!total;
    bt.textContent=importando?'Importando…':job?.importado?'Atualizar no CRM':'Importar para o CRM';
    $('#scExport').disabled=!lista.length;
    const info=$('#scImported');info.replaceChildren();
    if(job?.busca_id){
      const a=document.createElement('a');a.className='btn sm';a.href=job.na_lixeira?'#/lixeira':`#/buscas/${encodeURIComponent(job.busca_id)}`;
      a.textContent=job.na_lixeira?'Restaurar na lixeira':'Ver busca no CRM';info.append(a);
    }
    const paginas=Math.max(1,Math.ceil(lista.length/50));estado.pagina=Math.min(estado.pagina,paginas-1);
    $('#scRows').innerHTML=lista.slice(estado.pagina*50,estado.pagina*50+50).map(e=>{
      const site=urlSegura(e.site),inCRM=!!S.map[e.id];
      return `<tr><td><b class="lead-n">${esc(e.nome)}</b><div class="lead-c">${esc(e.categoria)}</div></td>
        <td>${esc(e.bairro||e.cidade||'—')}</td><td class="num">${esc(fNota(e.nota))}</td>
        <td>${esc(e.telefone||'—')}${e.whatsapp?'<span class="sc-wa">WhatsApp</span>':''}</td>
        <td>${site?`<a href="${esc(site)}" target="_blank" rel="noopener noreferrer">${esc(dominio(site))}</a>`:'<span class="muted">Sem site</span>'}</td>
        <td>${inCRM?`<button class="btn sm" data-sc-lead="${esc(e.id)}">Abrir ficha</button>`:'<span class="muted sm">Ainda não importado</span>'}</td></tr>`;
    }).join('')||`<tr><td colspan="6" class="empty">${total?'Nenhuma empresa corresponde ao filtro.':'Os resultados aparecem aqui enquanto o scraper trabalha.'}</td></tr>`;
    $('#scPageInfo').textContent=`${fN(lista.length)} empresas · página ${estado.pagina+1} de ${paginas}`;
    $('#scPrev').disabled=estado.pagina===0;$('#scNext').disabled=estado.pagina+1>=paginas;
    ScraperMapa.desenhar(lista,job,`${estado.selecionada}:${estado.filtro}`);
  }
  async function atualizar(token=epoca){
    if(!ativa(token)||carregando)return;
    carregando=true;
    try{
      const data=await api('/api/scraper/jobs');if(!ativa(token))return;
      estado.jobs=data.jobs;estado.conectado=true;
      if(!jobAtual())estado.selecionada=estado.jobs[0]?.id||'';
      const html=estado.jobs.map(j=>`<option value="${esc(j.id)}">${esc(j.nome)} · ${esc(etapas[j.status]||j.status)}${j.importado?' · no CRM':''}</option>`).join('');
      const select=$('#scJob');
      if(select.innerHTML!==html)select.innerHTML=html||'<option value="">Nenhuma busca ainda</option>';
      select.value=estado.selecionada;
      $('#scConnection').textContent='Scraper conectado';$('#scConnection').className='sc-connection on';
      if(estado.selecionada){
        const id=estado.selecionada;
        const result=await api(`/api/scraper/jobs/${encodeURIComponent(id)}/resultados`);
        if(!ativa(token)||id!==estado.selecionada)return;
        estado.empresas=result.empresas;ls.set('sithScraperJob',id);
        const job=jobAtual();
        if(!importando)mensagem(job?.na_lixeira?'Essa busca está na lixeira. Restaure-a para reimportar.':
          job?.status==='failed'?'A busca falhou. Reduza a quantidade e tente uma nova busca.':
          job?.status==='ok'?'Busca concluída. Importe para trabalhar os leads no funil.':
          'Buscando empresas. Você pode continuar usando as outras áreas da central.');
      }else{estado.empresas=[];mensagem('Faça uma busca no mapa ou use a busca avançada. Os resultados ficam disponíveis para importar.');}
      atualizarResumo();
    }catch(error){
      if(!ativa(token))return;
      estado.conectado=false;
      $('#scConnection').textContent='Scraper indisponível';$('#scConnection').className='sc-connection';
      mensagem(error.message,true);
      atualizarResumo();
    }finally{if(token===epoca)carregando=false;}
  }
  async function importar(){
    const job=jobAtual(),token=epoca;if(!job||importando||job.status!=='ok')return;
    importando=true;atualizarResumo();
    try{
      const data=await api(`/api/scraper/jobs/${encodeURIComponent(job.id)}/importar`,{method:'POST',body:{}});
      await Promise.all([carregaLeads(),carregaBuscas()]);renderNav();
      toast(`${fN(data.novos)} novos leads; ${fN(data.atualizados)} atualizados no CRM.`);
      if(ativa(token)){
        job.importado=true;job.busca_id=data.busca_id;atualizarResumo();
        mensagem(`Importação salva: ${fN(data.total)} empresas, ${fN(data.novos)} novas. Status e anotações preservados.`);
      }
    }catch(error){if(ativa(token))mensagem(error.message,true);}
    finally{importando=false;if(ativa(token))atualizarResumo();}
  }
  async function criar(event){
    event.preventDefault();if(criando)return;
    const token=epoca,form=event.currentTarget,fd=new FormData(form);
    const data={nichos:fd.get('nichos'),local:fd.get('local'),quantidade:Number(fd.get('quantidade')),
      raio:Number(fd.get('raio')),idioma:fd.get('idioma'),emails:fd.has('emails'),tempo:fd.get('tempo')};
    criando=true;$('#scGo').disabled=true;$('#scGo').textContent='Localizando e iniciando…';mensagem('Preparando a busca…');
    try{
      const result=await api('/api/scraper/jobs',{method:'POST',body:data});
      ls.set('sithScraperForm',data);estado.selecionada=result.id;estado.empresas=[];estado.pagina=0;
      toast('Busca iniciada. Acompanhe as empresas no mapa.');
      if(ativa(token))await atualizar(token);
    }catch(error){if(ativa(token))mensagem(error.message,true);}
    finally{criando=false;if(ativa(token)){$('#scGo').disabled=false;$('#scGo').textContent='Buscar empresas';}}
  }
  function abrir(arg){
    fechar();const token=epoca;
    if(arg)estado.selecionada=arg;
    crumbs([['Prospecção','#/inicio'],['Scraper com mapa']]);
    const salvo=ls.get('sithScraperForm',{});
    $('#page').innerHTML=`<div class="ph"><div><h1>Encontre seu próximo cliente.</h1><p>Busque no mapa e leve as empresas direto para o seu CRM.</p></div>
      <div class="acts"><a class="btn" href="#/nova">${ic('plus')}Busca avançada</a><a class="btn" href="#/funil">${ic('kanban')}Abrir funil</a></div></div>
      <div id="scRoot"><div class="sc-layout"><details class="card sc-options" open><summary>Nova busca no mapa</summary>
      <form id="scForm" class="card-b"><label class="lbl" for="scNicho">O que você procura?</label>
        <input class="in" id="scNicho" name="nichos" placeholder="Ex.: dentistas, clínicas" required minlength="2" maxlength="300" value="${esc(salvo.nichos||'')}">
        <label class="lbl" for="scLocal">Bairro e cidade</label><input class="in" id="scLocal" name="local" placeholder="Ex.: Centro, Guarujá, SP" required minlength="3" maxlength="200" value="${esc(salvo.local||'')}">
        <label class="lbl" for="scQty">Quantidade aproximada</label><select class="in" id="scQty" name="quantidade">${[20,60,120,200].map(n=>`<option value="${n}" ${n===(salvo.quantidade||60)?'selected':''}>${n===200?'200+':n} empresas</option>`).join('')}</select>
        <label class="lbl" for="scRadius">Raio da busca <output id="scRadiusValue">${Number(salvo.raio)||5} km</output></label>
        <input id="scRadius" name="raio" type="range" min="1" max="30" value="${Number(salvo.raio)||5}">
        <div class="sc-two"><div><label class="lbl" for="scLang">Idioma</label><select class="in" id="scLang" name="idioma"><option value="pt">Português</option><option value="en">English</option><option value="es">Español</option></select></div>
        <div><label class="lbl" for="scTime">Tempo limite</label><select class="in" id="scTime" name="tempo"><option value="auto">Automático</option><option value="600">10 min</option><option value="1200">20 min</option><option value="2400">40 min</option><option value="3600">1 hora</option></select></div></div>
        <label class="switch sc-email"><input type="checkbox" name="emails" ${salvo.emails?'checked':''}>Buscar e-mails nos sites</label>
        <p class="hint">A visita aos sites aumenta o tempo da busca. A quantidade é uma estimativa.</p>
        <button class="btn pri lg" id="scGo" type="submit">Buscar empresas</button>
        <p class="sc-flow">Mapa → Base de leads → Funil → Atendimento</p>
      </form></details>
      <section class="card sc-map-card" aria-label="Resultados no mapa"><div class="sc-map-toolbar"><label for="scJob">Suas buscas</label>
        <select id="scJob" class="in"><option>Carregando buscas…</option></select><button class="btn sm" type="button" id="scRefresh" aria-label="Atualizar buscas">${ic('refresh')}</button></div>
        <div class="sc-map-wrap"><div id="scMap" aria-label="Mapa das empresas encontradas"></div><span class="sc-map-note" id="scMapNote">O mapa acompanha a busca selecionada</span></div>
        <div class="sc-map-status"><span id="scConnection" class="sc-connection">Conectando…</span><span id="scJobState">Escolha uma busca</span></div>
      </section></div>
      <section class="card sc-results"><div class="sc-result-head"><div><h2>Empresas encontradas</h2><p>Importar reúne os resultados à sua base e mantém o histórico de cada lead.</p></div>
        <div class="row sc-import-actions"><span id="scImported"></span><button id="scImport" class="btn pri" disabled>Importar para o CRM</button></div></div>
        <div class="sc-numbers"><div><b id="scTotal">0</b><span>Empresas</span></div><div><b id="scWhats">0</b><span>Com WhatsApp</span></div><div><b id="scSemSite">0</b><span>Sem site</span></div><div><b id="scEmails">0</b><span>Com e-mail</span></div></div>
        <div id="scNotice" class="sc-notice" role="status" aria-live="polite">Carregando…</div>
        <div class="tbar"><label for="scFilter">Mostrar</label><select class="in" id="scFilter"><option value="todas">Todas</option><option value="sem_site">Sem site</option><option value="social">Só rede social</option><option value="whatsapp">Com WhatsApp</option><option value="email">Com e-mail</option></select>
          <label class="sc-sr" for="scText">Filtrar empresas</label><input id="scText" type="search" class="in" placeholder="Filtrar por nome ou bairro"><button class="btn sm" id="scExport" disabled>${ic('down')}Baixar planilha</button></div>
        <div class="twrap"><table class="t"><thead><tr><th>Empresa</th><th>Local</th><th>Nota</th><th>Telefone</th><th>Site</th><th>CRM</th></tr></thead><tbody id="scRows"></tbody></table></div>
        <div class="pag"><span id="scPageInfo"></span><div class="row"><button class="btn sm" id="scPrev">Anterior</button><button class="btn sm" id="scNext">Próxima</button></div></div>
      </section></div>`;
    $('#scLang').value=salvo.idioma||'pt';$('#scTime').value=salvo.tempo||'auto';
    $('#scFilter').value=estado.filtro;$('#scText').value=estado.texto;
    $('#scForm').onsubmit=criar;$('#scImport').onclick=importar;$('#scRefresh').onclick=()=>atualizar(token);
    $('#scJob').onchange=()=>{estado.selecionada=$('#scJob').value;estado.empresas=[];estado.pagina=0;atualizarResumo();atualizar(token);};
    $('#scRadius').oninput=e=>$('#scRadiusValue').textContent=e.target.value+' km';
    $('#scFilter').onchange=e=>{estado.filtro=e.target.value;estado.pagina=0;atualizarResumo();};
    $('#scText').oninput=e=>{estado.texto=e.target.value;estado.pagina=0;atualizarResumo();};
    $('#scPrev').onclick=()=>{estado.pagina--;atualizarResumo();};$('#scNext').onclick=()=>{estado.pagina++;atualizarResumo();};
    $('#scExport').onclick=()=>exportaCsv(filtradas().map(e=>({...e,status:S.map[e.id]?.status||'novo',obs:S.map[e.id]?.obs||''})),'scraper');
    $('#scRoot').onclick=e=>{const b=e.target.closest('[data-sc-lead]');if(b)abreLead(b.dataset.scLead);};
    ScraperMapa.abrir($('#scMap'));atualizar(token);
    timer=setInterval(()=>{if(!document.hidden)atualizar(token);},6000);
  }
  return {abrir,fechar};
})();
VIEWS.scraper=ScraperUI.abrir;
