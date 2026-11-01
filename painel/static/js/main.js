// Prospecta: status, atualização automática e inicialização (carrega por último). Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ status + atualização automática ═════════════
async function status(){
  try{ const s=await api("/api/status");
    $("#dot").className="dot "+(s.motor?"ok":"off");
    $("#motorTxt").textContent = s.motor?"Motor ligado":"Motor desligado";
    $("#motorSub").textContent = s.motor?"Roda 100% no seu computador":"Reabra o Prospeccao.cmd";
  }catch{ $("#dot").className="dot off"; $("#motorTxt").textContent="Painel desconectado"; $("#motorSub").textContent="Reabra o Prospeccao.command"; }
}
async function tick(){
  if(document.hidden) return;
  const concluiu = await carregaBuscas();
  if(concluiu){ await carregaLeads(); toast("Busca concluída! Leads novos na base."); }
  const naoLidasAntes = S.naoLidas||0; await carregaConversas();
  if((S.naoLidas||0) > naoLidasAntes) toast("Nova mensagem no WhatsApp");
  renderNav();
  if(leadAberto) return; // não mexe na tela com a ficha aberta
  const {v, arg} = rota();
  if(v==="whatsapp" && document.activeElement?.id!=="cvT"){
    // redesenha só se algo mudou (conversa nova, IA respondeu, QR trocou)
    let wa={}; try{ wa = await api("/api/wa/status"); }catch{}
    const sig = JSON.stringify([wa.conexao, wa.qr?.length, (S.conversas||[]).map(c=>[c.numero,c.ultima_em,c.ia,c.aguardando_ia])]);
    if(sig !== VIEWS.whatsapp._assinatura) VIEWS.whatsapp(arg);
    return;
  }
  const ativa = S.buscas.some(b=>b.estado==="rodando"||b.estado==="na_fila");
  if(v==="buscas" && (ativa || concluiu)) VIEWS.buscas(arg);
  else if(v==="inicio" && (ativa || concluiu)) VIEWS.inicio();
  else if(concluiu && (v==="leads" || v==="funil")) render();
}
(async () => {
  try{ const a = await (await fetch("/api/auth/estado")).json(); if(!a.logado) return mostraLogin(); }catch{}
  await Promise.all([carregaBuscas(), carregaLeads(), carregaConversas(), carregaLixeira(), status(), api("/api/config").then(c=>S.config=c).catch(()=>{})]);
  render();
  setInterval(tick, 3000);
  setInterval(status, 15000);
})();
