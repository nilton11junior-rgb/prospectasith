// Mapa da central. Ciclo de vida isolado para não manter timers/camadas ao sair da tela.
const ScraperMapa = (() => {
  let mapa, pontos, area, ultimaSelecao;
  const coord = e => e.latitude !== null && e.longitude !== null &&
    Number.isFinite(e.latitude) && Number.isFinite(e.longitude) && !(e.latitude === 0 && e.longitude === 0);
  function fechar(){
    if(mapa) mapa.remove();
    mapa=null; pontos=null; area=null; ultimaSelecao=null;
  }
  function abrir(el){
    fechar();
    if(!window.L){ el.textContent='Mapa indisponível. A lista e a importação continuam disponíveis.'; return; }
    mapa=L.map(el,{zoomControl:false,scrollWheelZoom:false}).setView([-23.5505,-46.6333],11);
    L.control.zoom({position:'bottomright'}).addTo(mapa);
    const aviso=$('#scMapFalha');
    const tilesComFalha=new Set();
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:19,
      referrerPolicy:'strict-origin',
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
    }).on('tileerror',({tile})=>{
      tile.style.visibility='hidden';
      tilesComFalha.add(tile);
      aviso.hidden=false;
    }).on('tileunload',({tile})=>{
      tilesComFalha.delete(tile);
      aviso.hidden=tilesComFalha.size===0;
    }).addTo(mapa);
    pontos=L.layerGroup().addTo(mapa);
    setTimeout(()=>{if(mapa && el.isConnected) mapa.invalidateSize();},100);
  }
  function desenhar(empresas, job, selecao){
    if(!mapa) return;
    pontos.clearLayers();
    const visiveis=empresas.filter(coord).slice(0,1000);
    for(const e of visiveis){
      const site=urlSegura(e.site), maps=urlSegura(e.maps);
      const popup=`<div class="sc-popup"><b>${esc(e.nome)}</b><p>${esc(e.categoria)}<br>${esc(e.endereco)}</p>
        <p>${e.nota?`${esc(fNota(e.nota))} · ${fN(e.avaliacoes)} avaliações<br>`:''}${esc(e.telefone)}</p>
        ${site?`<a href="${esc(site)}" target="_blank" rel="noopener noreferrer">Visitar site</a>`:''}
        ${maps?`<a href="${esc(maps)}" target="_blank" rel="noopener noreferrer">Ver no Google Maps</a>`:''}
        ${S.map[e.id]?`<button class="btn sm" data-sc-lead="${esc(e.id)}">Abrir ficha no CRM</button>`:''}</div>`;
      L.marker([e.latitude,e.longitude],{title:e.nome,
        icon:L.divIcon({className:'sc-marker',html:'<span class="sc-pin"></span>',iconSize:[18,18],iconAnchor:[9,9]})
      }).bindPopup(popup).addTo(pontos);
    }
    const novaSelecao=selecao!==ultimaSelecao;
    const lat=Number(job?.lat),lon=Number(job?.lon),radius=Number(job?.raio);
    if(novaSelecao){
      if(area) mapa.removeLayer(area);
      area=null;
      if(job?.lat!=null && job?.lon!=null && Number.isFinite(lat) && Number.isFinite(lon) &&
         Math.abs(lat)<=90 && Math.abs(lon)<=180 && radius>0 && radius<=30000){
        area=L.circle([lat,lon],{radius,color:'#c692ff',fillColor:'#8f36dc',fillOpacity:.12,weight:1.5,dashArray:'5 6'}).addTo(mapa);
      }
      if(visiveis.length) mapa.fitBounds(L.latLngBounds(visiveis.map(e=>[e.latitude,e.longitude])),{padding:[30,30],maxZoom:15,animate:false});
      else if(area) mapa.fitBounds(area.getBounds(),{padding:[24,24],animate:false});
      ultimaSelecao=selecao;
    }
    const nota=$('#scMapNote');
    if(nota) nota.textContent=visiveis.length===1000?'Mapa limitado a mil pontos. Use os filtros para refinar.':`${fN(visiveis.length)} ${visiveis.length===1?'empresa':'empresas'} com localização no mapa`;
  }
  return {abrir,desenhar,fechar,coord};
})();
