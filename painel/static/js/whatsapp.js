// Prospecta: login e WhatsApp interno. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ LOGIN ═════════════
let loginAberto = false;
async function mostraLogin(){
  if(loginAberto) return; loginAberto = true;
  let st = {configurado:true}; try{ st = await (await fetch("/api/auth/estado")).json(); }catch{}
  const criar = !st.configurado;
  $("#lgSub").textContent = criar ? "Crie a senha de acesso ao painel" : "Entre para continuar";
  $("#lgS2").style.display = criar ? "" : "none";
  $("#lgB").textContent = criar ? "Criar senha e entrar" : "Entrar";
  $("#lgH").textContent = criar ? "Mínimo de 6 caracteres. Ela protege seus leads e o WhatsApp, inclusive no acesso pelo celular." : "";
  $("#login").classList.add("on"); $("#lgS").focus();
  $("#lgF").onsubmit = async e => { e.preventDefault();
    const senha = $("#lgS").value;
    if(criar && senha !== $("#lgS2").value) return $("#lgH").textContent = "As senhas não são iguais.";
    const r = await fetch(criar?"/api/auth/criar":"/api/auth/entrar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({senha})});
    const j = await r.json().catch(()=>({}));
    if(!r.ok) return $("#lgH").textContent = j.erro || "Não deu certo.";
    location.reload(); };
}
async function sair(){ await fetch("/api/auth/sair",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); location.reload(); }

// ═════════════ WHATSAPP INTERNO ═════════════
const QUEM = {lead:"", eu:"Você", ia:"IA", auto:"Disparo automático", followup:"Follow-up automático"};
const SEG_NOME = {reputacao:"Nota baixa no Google", sem_presenca:"Sem site e sem Instagram", so_instagram:"Só Instagram", site_sem_instagram:"Site sem Instagram", site_e_instagram:"Site e Instagram"};
async function carregaConversas(){ try{ S.conversas = await api("/api/conversas"); S.naoLidas = S.conversas.reduce((a,c)=>a+(c.nao_lidas||0),0); }catch{} }
VIEWS.whatsapp = async (numero) => {
  crumbs([["Atendimento"],["WhatsApp interno"]]);
  let wa = {}; try{ wa = await api("/api/wa/status"); }catch(e){ wa = {erro:e.message}; }
  await carregaConversas();
  let cv = null; if(numero){ try{ cv = await api(`/api/conversas/${numero}`); if(cv.nao_lidas) api(`/api/conversas/${numero}/lida`,{method:"POST"}); }catch{} }
  if(rota().v!=="whatsapp") return;
  const conexao = wa.conexao==="conectado" ? `<div class="row"><span class="dot ok"></span><b>Conectado</b><span class="muted sm">${wa.numero?fTel(wa.numero):""}${wa.nome?" · "+esc(wa.nome):""}</span></div>
      <div class="row" style="margin-top:10px"><button class="btn sm" id="waSair">${ic("out")}Desconectar</button></div>`
    : wa.conexao==="qr" && wa.qr ? `<div class="qr"><img src="${wa.qr}" alt="QR Code do WhatsApp"><div class="sm muted" style="text-align:center">No celular: WhatsApp → <b>Dispositivos conectados</b> → <b>Conectar dispositivo</b> e aponte para o código.</div></div>`
    : wa.servico ? `<div class="row"><span class="dot"></span><b>${{iniciando:"Iniciando…",parado:"Desconectado",erro:"QR Code venceu",sem_sessao:"Não conectado"}[wa.conexao]||esc(wa.conexao)}</b></div>
      <div class="row" style="margin-top:10px"><button class="btn pri sm" id="waCon">${ic("wa")}Conectar WhatsApp</button></div>`
    : `<div class="note err">${ic("flag")}<span>Serviço de WhatsApp desligado. Abra o sistema pelo <b>Prospeccao.cmd</b>.${wa.erro?`<br><small>${esc(wa.erro)}</small>`:""}</span></div>`;
  const lista = (S.conversas||[]).map(c=>`<a class="it ${cv&&cv.numero===c.numero?"on":""}" href="#/whatsapp/${c.numero}"><div class="row"><b>${esc(c.nome||fTel(c.numero))}</b>${c.nao_lidas?`<span class="un">${c.nao_lidas}</span>`:""}</div>
      <p>${c.ultima_de&&c.ultima_de!=="lead"?esc(QUEM[c.ultima_de])+": ":""}${esc(c.ultima)}</p><div class="xs muted">${c.ia?"IA ligada":"IA desligada"}${c.aguardando_ia?" · respondendo…":""} · ${fRel(c.ultima_em)}</div></a>`).join("");
  $("#page").innerHTML = `<div class="ph fade"><div><h1>WhatsApp interno</h1><p>Conecte seu aparelho pelo QR Code e acompanhe as conversas com os leads. Conversas pessoais e grupos nunca entram aqui.</p></div></div>
    <div class="wa-grid fade">
      <div class="grid" style="gap:16px">
        <div class="card"><div class="card-h"><h3>Conexão</h3></div><div class="card-b">${conexao}</div></div>
        <div class="card cv-list" style="overflow:hidden"><div class="card-h"><h3>Conversas</h3></div>${lista||`<div class="empty" style="padding:30px 14px"><b>Nenhuma conversa ainda</b>Elas aparecem quando você ou o disparo automático manda a primeira mensagem para um lead.</div>`}</div>
      </div>
      <div class="card">${cv?`<div class="chat">
        <div class="card-h"><h3 style="cursor:pointer" id="cvLead">${esc(cv.nome||fTel(cv.numero))}</h3>${pillSt(cv.status)}<div class="sp"></div>
          <label class="switch"><input type="checkbox" id="cvIa" ${cv.ia?"checked":""}> IA responde</label></div>
        ${cv.ia_motivo&&!cv.ia?`<div class="note info" style="margin:0 14px 8px">${ic("flag")}<span>${esc(cv.ia_motivo)}</span></div>`:""}
        ${cv.ia_erro?`<div class="note err" style="margin:0 14px 8px">${ic("flag")}<span>A IA falhou: ${esc(cv.ia_erro)}</span></div>`:""}
        <div class="chat-b" id="cvB">${cv.msgs.map(m=>`<div class="msg ${m.de}">${m.de!=="lead"&&m.de!=="eu"?`<span class="tag">${QUEM[m.de]}</span>`:""}${esc(m.txt)}<small>${fData(m.t).slice(9)}</small></div>`).join("")}</div>
        <form class="chat-f" id="cvF"><textarea class="in" id="cvT" rows="2" placeholder="Escreva uma mensagem…"></textarea><button class="btn wa">${ic("send")}Enviar</button></form>
      </div>`:`<div class="empty" style="padding:80px 20px"><div class="ic">${ic("wa")}</div><b>Escolha uma conversa</b>Ou vá em <a href="#/agente">Agente IA</a> para escolher um lead e mandar a primeira mensagem.</div>`}</div>
    </div>`;
  $("#waCon") && ($("#waCon").onclick = async () => { try{ await api("/api/wa/conectar",{method:"POST"}); toast("Gerando QR Code…"); setTimeout(()=>render(),2500); }catch(e){ toast(e.message); } });
  $("#waSair") && ($("#waSair").onclick = async () => { if(!confirma("wasair","Desconectar o WhatsApp deste painel?")) return; await api("/api/wa/sair",{method:"POST"}); toast("Desconectado"); setTimeout(()=>render(),1500); });
  if(cv){
    const b=$("#cvB"); b.scrollTop=b.scrollHeight;
    $("#cvLead").onclick = () => abreLead(cv.lead_id);
    $("#cvIa").onchange = async e => { await api(`/api/conversas/${cv.numero}/ia`,{method:"POST",body:{ativa:e.target.checked}}); toast(e.target.checked?"IA ligada nesta conversa":"IA desligada nesta conversa"); };
    $("#cvT").onkeydown = e => { if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); $("#cvF").requestSubmit(); } };
    $("#cvF").onsubmit = async e => { e.preventDefault(); const t=$("#cvT").value.trim(); if(!t) return; $("#cvT").disabled=true;
      try{ await api("/api/wa/enviar",{method:"POST",body:{numero:cv.numero,texto:t}}); render(); }catch(err){ toast(err.message); $("#cvT").disabled=false; } };
  }
  VIEWS.whatsapp._assinatura = JSON.stringify([wa.conexao, wa.qr?.length, (S.conversas||[]).map(c=>[c.numero,c.ultima_em,c.ia,c.aguardando_ia])]);
};

