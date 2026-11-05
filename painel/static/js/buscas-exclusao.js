// Exclusão permanente: seleção explícita -> resumo do servidor -> confirmação.
const ExclusaoBuscas = (() => {
  const selecionadas = new Set();
  let aberta = false;
  const ativa = b => ['rodando','na_fila'].includes(b.estado);
  function preparar(bs){
    for(const id of selecionadas) if(!bs.some(b=>b.id===id&&!ativa(b))) selecionadas.delete(id);
  }
  function contagem(){
    const bt=$('#excluirSelecionadas');
    if(bt){bt.disabled=!selecionadas.size;bt.textContent=`Excluir selecionadas${selecionadas.size?` (${selecionadas.size})`:''}`;}
    const todos=$('#selecionarBuscas'), checks=$$('[data-selecionar-busca]:not(:disabled)');
    if(todos){todos.checked=!!checks.length&&checks.every(c=>c.checked);todos.indeterminate=checks.some(c=>c.checked)&&!todos.checked;}
  }
  function ligar(bs){
    $$('[data-selecionar-busca]').forEach(c=>{
      c.checked=selecionadas.has(c.dataset.selecionarBusca);
      c.onclick=e=>e.stopPropagation();
      c.onchange=()=>{c.checked?selecionadas.add(c.dataset.selecionarBusca):selecionadas.delete(c.dataset.selecionarBusca);contagem();};
    });
    $('#selecionarBuscas')?.addEventListener('change',e=>{
      const marcar=e.target.checked;
      $$('[data-selecionar-busca]:not(:disabled)').forEach(c=>{c.checked=marcar;c.onchange();});contagem();
    });
    $$('[data-excluir-busca]').forEach(bt=>bt.onclick=e=>{e.stopPropagation();abrir([bt.dataset.excluirBusca]);});
    if($('#excluirSelecionadas')) $('#excluirSelecionadas').onclick=()=>abrir([...selecionadas]);
    if($('#excluirTodas')) $('#excluirTodas').onclick=()=>abrir(bs.map(b=>b.id));
    contagem();
  }
  async function abrir(ids){
    if(aberta||!ids.length)return;
    aberta=true;
    let dialog;
    try{
      const resumo=await api('/api/buscas/exclusao/previa',{method:'POST',body:{ids}});
      dialog=document.createElement('dialog');dialog.className='exclusao-dialog';
      dialog.setAttribute('aria-labelledby','exclusaoTitulo');
      dialog.innerHTML=`<form method="dialog"><div class="exclusao-body">
        <h2 id="exclusaoTitulo">Excluir ${resumo.buscas===1?'busca e leads':'buscas e leads'}?</h2>
        <p>Isso remove os registros de todas as áreas do CRM: histórico de buscas, base de leads, funil, conversas e agenda.</p>
        <div class="exclusao-resumo"><div><b>${fN(resumo.buscas)}</b><span>Buscas</span></div><div><b>${fN(resumo.leads)}</b><span>Leads</span></div>
        <div><b>${fN(resumo.conversas)}</b><span>Conversas locais</span></div><div><b>${fN(resumo.reservas)}</b><span>Reservas</span></div></div>
        ${resumo.compartilhados?`<p class="note err">${fN(resumo.compartilhados)} lead(s) também aparecem em outras buscas e serão removidos de lá.</p>`:''}
        ${resumo.trabalhados?`<p class="note">Inclui ${fN(resumo.trabalhados)} lead(s) com status, notas ou histórico já trabalhados.</p>`:''}
        <p class="muted sm">A exclusão não passa pela lixeira. Uma cópia de segurança local é criada antes de apagar. Mensagens no aplicativo WhatsApp não são apagadas.</p>
        <label class="exclusao-aceite"><input type="checkbox" id="exclusaoAceite">Entendi e quero excluir as buscas e todos esses dados vinculados.</label>
        <p id="exclusaoErro" class="exclusao-erro" role="alert"></p>
        </div><div class="exclusao-rodape"><button class="btn" id="exclusaoCancelar" autofocus>Cancelar</button>
        <button class="btn danger" id="exclusaoConfirmar" type="button" disabled>Excluir busca${resumo.buscas===1?'':'s'} e leads</button></div></form>`;
      document.body.append(dialog);dialog.showModal();
      let enviando=false;
      const aceitar=$('#exclusaoAceite',dialog), confirmar=$('#exclusaoConfirmar',dialog), cancelar=$('#exclusaoCancelar',dialog);
      dialog.addEventListener('cancel',e=>{if(enviando)e.preventDefault();});
      dialog.addEventListener('close',()=>{dialog.remove();aberta=false;});
      aceitar.onchange=()=>confirmar.disabled=!aceitar.checked;
      confirmar.onclick=async()=>{
        if(enviando||!aceitar.checked)return;
        enviando=true;confirmar.disabled=true;cancelar.disabled=true;aceitar.disabled=true;confirmar.textContent='Excluindo…';
        try{
          const resultado=await api('/api/buscas/exclusao',{method:'POST',body:{ids:resumo.ids,confirmacao:resumo.confirmacao}});
          resumo.ids.forEach(id=>selecionadas.delete(id));
          await Promise.all([carregaBuscas(),carregaLeads(),carregaConversas(),carregaLixeira(),api('/api/config').then(c=>S.config=c)]);
          dialog.close();renderNav();
          toast(`${fN(resultado.buscas)} busca(s) e ${fN(resultado.leads)} lead(s) excluídos.${resultado.limpeza_pendente?' Limpeza do motor agendada.':''}`);
          if(location.hash==='#/buscas')render();else location.hash='#/buscas';
        }catch(e){
          $('#exclusaoErro',dialog).textContent=e.message+' Feche e confira o resumo novamente antes de tentar.';
          confirmar.textContent='Confira o resumo novamente';
        }finally{enviando=false;cancelar.disabled=false;}
      };
    }catch(e){dialog?.remove();aberta=false;toast(e.message);}
  }
  return {preparar,ligar,abrir,selecionadas};
})();
