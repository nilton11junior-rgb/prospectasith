// Prospecta: utilidades, ícones, estado global e navegação. Scripts clássicos: compartilham o escopo global, a ordem importa.
// ═════════════ utilidades ═════════════
const $ = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const semAc = s => String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase();
const fN = n => Number(n||0).toLocaleString("pt-BR");
const fPct = (a,b) => b ? Math.round(a/b*100)+"%" : "—";
const fNota = n => n ? n.toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:1}) : "—";
const fData = t => t ? new Date(t*1000).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",year:"2-digit",hour:"2-digit",minute:"2-digit"}) : "";
function fRel(t){ if(!t) return ""; const s=Date.now()/1000-t;
  if(s<60) return "agora"; if(s<3600) return `há ${Math.floor(s/60)} min`; if(s<86400) return `há ${Math.floor(s/3600)} h`;
  if(s<86400*7) return `há ${Math.floor(s/86400)} dia${s>=172800?"s":""}`; return fData(t).slice(0,8); }
function fTel(d){ d=String(d||"").replace(/^55/,""); return d.length===11?`(${d.slice(0,2)}) ${d.slice(2,7)}-${d.slice(7)}`:d.length===10?`(${d.slice(0,2)}) ${d.slice(2,6)}-${d.slice(6)}`:d; }
// link vindo de dado de terceiro: só http/https (bloqueia javascript:, data: etc.)
const urlSegura = u => /^https?:\/\//i.test(String(u||"").trim()) ? String(u).trim() : (/^[\w.-]+\.[a-z]{2,}(\/|$)/i.test(String(u||"").trim()) ? "http://"+String(u).trim() : "");
function dominio(u){ try{ return new URL(u.startsWith("http")?u:"http://"+u).hostname.replace(/^www\./,""); }catch{ return u; } }
const ls = { get(k,d){ try{ const v=localStorage.getItem(k); return v==null?d:JSON.parse(v);}catch{return d} }, set(k,v){ try{ localStorage.setItem(k,JSON.stringify(v)); }catch{} } };
function toast(t){ const el=$("#toast"); el.textContent=t; el.classList.add("on"); clearTimeout(toast.t); toast.t=setTimeout(()=>el.classList.remove("on"),2400); }
async function api(path, opts={}){
  const r = await fetch(path, {headers:{"Content-Type":"application/json"}, ...opts, body: opts.body?JSON.stringify(opts.body):undefined});
  const j = await r.json().catch(()=>({}));
  if(r.status===401 && j.login){ mostraLogin(); throw new Error(j.erro); }
  if(!r.ok) throw new Error(j.erro || `Erro ${r.status}`);
  return j;
}
// confirmação sem diálogo nativo: o primeiro clique arma, o segundo (em até 4s) confirma
function confirma(chave, msg){ const t=Date.now(); if(confirma.k===chave && t-confirma.t<4000){ confirma.k=null; return true; }
  confirma.k=chave; confirma.t=t; toast(msg+" Clique de novo para confirmar."); return false; }

const I = {
  home:'<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  hist:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
  users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.3a3.5 3.5 0 0 1 0 7.4M21.5 20a6.5 6.5 0 0 0-4-6"/>',
  kanban:'<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="11" rx="1.5"/><rect x="17" y="4" width="4" height="7" rx="1.5"/>',
  msg:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z"/>',
  gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  wa:'<path d="M3.5 20.5l1.3-4.4A8.5 8.5 0 1 1 8 19.3z"/><path d="M9 8.5c0 3.5 3 6.5 6.5 6.5l1.2-1.6-2-1-1 .8c-1-.4-2.5-1.9-2.9-2.9l.8-1-1-2z"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  ig:'<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".6" fill="currentColor"/>',
  phone:'<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  pin:'<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.4"/>',
  x:'<path d="M18 6 6 18M6 6l12 12"/>',
  down:'<path d="M12 4v12m0 0-5-5m5 5 5-5M4 20h16"/>',
  copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  note:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  flag:'<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  spark:'<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  trend:'<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
  check:'<path d="m5 12 5 5L20 7"/>',
  refresh:'<path d="M20 11a8 8 0 0 0-14.8-4M4 4v4h4M4 13a8 8 0 0 0 14.8 4M20 20v-4h-4"/>',
  chev:'<path d="m6 9 6 6 6-6"/>',
  trash:'<path d="M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3"/>',
  cal:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  send:'<path d="M4 12 20 4l-6 16-3-7z"/><path d="m11 13 9-9"/>',
  out:'<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
};
const ic = (n, cls="i") => `<svg class="${cls}" viewBox="0 0 24 24">${I[n]}</svg>`;

const STATUS = [["novo","Novo"],["contatado","Contatado"],["respondeu","Respondeu"],["reuniao","Reunião marcada"],["fechado","Fechou negócio"],["descartado","Descartado"]];
const NOME_ST = Object.fromEntries(STATUS);
const COR_ST = {novo:"var(--muted)",contatado:"var(--blue)",respondeu:"var(--warn)",reuniao:"var(--violet)",fechado:"var(--green)",descartado:"var(--err)"};
const pillSt = s => `<span class="pill s-${s}">${NOME_ST[s]||s}</span>`;
const TAM = {rapida:["Rápida","~20","2 min"], padrao:["Padrão","60–120","5–10 min"], completa:["Completa","até 120","10–15 min"], cidade:["Cidade inteira","200–600","30–60 min"]};
const ESTADO = {na_fila:"Na fila", rodando:"Rodando", concluida:"Concluída", erro:"Erro", cancelada:"Cancelada"};

// ═════════════ estado global ═════════════
const S = { leads:[], map:{}, buscas:[], config:null, municipios:[] };
async function carregaLeads(){ try{ S.leads = await api("/api/leads"); S.map = Object.fromEntries(S.leads.map(l=>[l.id,l])); }catch{} }
async function carregaBuscas(){
  const antes = Object.fromEntries(S.buscas.map(b=>[b.id,b.estado]));
  try{ S.buscas = await api("/api/buscas"); }catch{ return false; }
  return S.buscas.some(b => antes[b.id] && antes[b.id]!==b.estado && b.estado==="concluida");
}
function upsertLead(l){ const p = {...l, n_hist:(l.historico||[]).length}; delete p.historico;
  S.map[l.id] = p; const i = S.leads.findIndex(x=>x.id===l.id); if(i>=0) S.leads[i]=p; else S.leads.push(p); }

// ═════════════ navegação ═════════════
// menu: "Início" solto e grupos que abrem/fecham. Item = [rota, rótulo, ícone]. Cada área nova entra como um grupo aqui.
const NAV = [
  {solto:["inicio","Início","home"]},
  {id:"prospeccao", nome:"Prospecção", ic:"search", itens:[["nova","Nova busca","plus"],["buscas","Buscas","hist"],["leads","Leads","users"],["funil","Funil de vendas","kanban"],["lixeira","Lixeira","trash"]]},
  {id:"atendimento", nome:"Atendimento", ic:"msg", itens:[["whatsapp","WhatsApp interno","wa"],["campanhas","Campanhas","send"],["agente","Agente IA","spark"],["agenda","Agenda","cal"]]},
  {id:"ajustes", nome:"Ajustes", ic:"gear", itens:[["mensagens","Mensagens","msg"],["config","Configurações","gear"]]},
];
const NAV_ABERTOS = ls.get("navAbertos", {});   // grupo -> true/false escolhido por você; o grupo da tela atual sempre abre
function rota(){ const h = location.hash.replace(/^#\/?/,"") || "inicio"; const [v, ...r] = h.split("/"); return {v, arg:r.join("/")}; }
// avisos por item: n = número, aviso = conta no resumo do grupo fechado (leads é só informação)
function avisoDe(r){
  if(r==="buscas"){ const n = S.buscas.filter(b=>b.estado==="rodando"||b.estado==="na_fila").length; return n && {n, cls:"pulse", aviso:true}; }
  if(r==="lixeira") return S.nLixeira && {n:S.nLixeira, cls:"mudo", aviso:true};
  if(r==="whatsapp") return S.naoLidas && {n:S.naoLidas, cls:"", aviso:true};
  if(r==="leads") return S.leads.length && {n:fN(S.leads.length), cls:"mudo", aviso:false};
  return 0;
}
const badgeHtml = a => a ? `<span class="badge ${a.cls}">${a.n}</span>` : "";
function renderNav(){
  const {v} = rota();
  const link = ([r,nome,ico]) => `<a href="#/${r}" class="${v===r?"on":""}" ${v===r?'aria-current="page"':""}>${ic(ico)}${nome}${badgeHtml(avisoDe(r))}</a>`;
  const html = NAV.map(g => {
    if(g.solto) return link(g.solto);
    const atual = g.itens.some(i=>i[0]===v), aberto = atual || NAV_ABERTOS[g.id]===true;
    const total = g.itens.reduce((t,i)=>{ const a = avisoDe(i[0]); return t + (a && a.aviso ? Number(a.n)||0 : 0); }, 0);
    return `<div class="nav-grp ${aberto?"open":""} ${atual?"atual":""}" data-g="${g.id}">
      <button type="button" class="nav-h" aria-expanded="${aberto}" aria-controls="sub-${g.id}">${ic(g.ic)}${g.nome}
        <span class="nav-fim">${total?`<span class="badge resumo">${total}</span>`:""}${ic("chev","i chev")}</span></button>
      <div class="nav-sub" id="sub-${g.id}"><div class="nav-in" ${aberto?"":"inert"}>${g.itens.map(link).join("")}</div></div></div>`;
  }).join("");
  if(html !== renderNav.ult){ $("#nav").innerHTML = html; renderNav.ult = html; }   // sem refazer à toa: preserva foco e animação
}
// abrir/fechar: mexe no elemento existente (a animação roda) e guarda a escolha
$("#nav").addEventListener("click", e => {
  const h = e.target.closest(".nav-h"); if(!h) return;
  const g = h.parentElement;
  if(g.classList.contains("atual")) return;   // o grupo da tela atual fica sempre aberto
  const abre = !g.classList.contains("open");
  g.classList.toggle("open", abre); h.setAttribute("aria-expanded", abre);
  $(".nav-in", g).toggleAttribute("inert", !abre);
  NAV_ABERTOS[g.dataset.g] = abre; ls.set("navAbertos", NAV_ABERTOS);
  renderNav.ult = null;   // o próximo desenho reflete a escolha
});
function crumbs(parts){ $("#crumbs").innerHTML = parts.map((p,i)=> i<parts.length-1 ? (p[1]?`<a href="${p[1]}">${esc(p[0])}</a>`:`<span>${esc(p[0])}</span>`)+`<span>/</span>` : `<b>${esc(p[0])}</b>`).join(""); }
const VIEWS = {};
function render(){
  const {v, arg} = rota();
  $("#side").classList.remove("open");
  renderNav();
  (VIEWS[v] || VIEWS.inicio)(arg);
}
window.addEventListener("hashchange", () => { render(); window.scrollTo(0,0); });
$("#hamb").onclick = () => $("#side").classList.toggle("open");
$("#gq").addEventListener("keydown", e => { if(e.key==="Enter"){ FL.texto = e.target.value; ls.set("fl",FL); if(rota().v==="leads") render(); else location.hash="#/leads"; } });

