/* CórnersPicks — renderizado de estadísticas desde data/*.json */
const NEON='#7CFF2E',GRASS='#2fbf4a',RED='#ff5a5a',AMBER='#ffc542',MUTED='#9fb7a4',BLUE='#4cc9f0';
if(window.Chart){Chart.defaults.color=MUTED;Chart.defaults.font.family='Montserrat, sans-serif';Chart.defaults.borderColor='#1f3a26';}
const nf=(x,d=1)=>x==null?'—':Number(x).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});
const uf=x=>x==null?'—':(x>0?'+':'')+nf(x,2)+' u';
const pf=x=>x==null?'—':nf(x,1)+' %';
const $=s=>document.querySelector(s);
async function getJSON(p){const r=await fetch(p,{cache:'no-store'});if(!r.ok)throw new Error(p+' '+r.status);return r.json();}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fdate=d=>{if(!d)return'';const[y,m,dd]=d.slice(0,10).split('-');return `${dd}/${m}`;};


/* ---------- Horas en la zona del visitante ---------- */
const TZ=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||undefined;}catch(e){return undefined;}})();
const _fb=iso=>iso?iso.slice(11,16)+' (UTC-5)':'—';           // respaldo si Intl falla
function _parts(iso,opts){const f=new Intl.DateTimeFormat('es',{timeZone:TZ,...opts});return Object.fromEntries(f.formatToParts(new Date(iso)).map(x=>[x.type,x.value]));}
function zoneShort(iso){try{return _parts(iso||new Date().toISOString(),{hour:'2-digit',timeZoneName:'short'}).timeZoneName||'';}catch(e){return 'UTC-5';}}
function lHora(iso){if(!iso)return'—';try{const p=_parts(iso,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'});return `${p.hour}:${p.minute}`;}catch(e){return _fb(iso);}}
function lHoraZ(iso){if(!iso)return'—';try{return `${lHora(iso)} ${zoneShort(iso)}`;}catch(e){return _fb(iso);}}
function lDay(iso){try{const p=new Intl.DateTimeFormat('en-CA',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(iso));const o=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${o.year}-${o.month}-${o.day}`;}catch(e){return (iso||'').slice(0,10);}}
function lFechaHora(iso){if(!iso)return'—';try{return `${fdate(lDay(iso))} ${lHora(iso)}`;}catch(e){return _fb(iso);}}
function lStamp(iso,txt){if(!iso)return txt||'—';try{const p=_parts(iso,{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZoneName:'short'});
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute} ${p.timeZoneName||''}`.trim();}catch(e){return (txt||iso)+' (UTC-5)';}}
function zoneLabel(){const z=zoneShort();return TZ?`${TZ.replace(/_/g,' ')}${z?' · '+z:''}`:'UTC-5';}
function localizeStatic(){document.querySelectorAll('time.lt[datetime]').forEach(t=>{try{t.textContent=t.dataset.z==='0'?lHora(t.dateTime):lHoraZ(t.dateTime);t.title='Hora de tu zona ('+zoneLabel()+')';}catch(e){}});
  document.querySelectorAll('[data-tz]').forEach(e=>e.textContent=zoneLabel());}

function kpis(el,s,extra=[]){
  const items=[['Picks resueltas',s.resueltas],['Aciertos',s.aciertos],['Errores',s.errores],['% acierto',pf(s.pct)],
    ['Unidades',uf(s.unidades),s.unidades<0],['ROI por pick',s.roi==null?'—':(s.roi>0?'+':'')+nf(s.roi,1)+' %',s.roi<0],['Pendientes',s.pendientes],...extra];
  el.innerHTML=items.map(([l,v,neg])=>`<div class="kpi"><div class="v${neg?' neg':''}">${v}</div><div class="l">${l}</div></div>`).join('');
}
function lineChart(id,serie,key,label,color,opts={}){
  const ds=[{label,data:serie.map(p=>p[key]),borderColor:color,backgroundColor:color+'33',fill:opts.fill??true,tension:.25,pointRadius:3}];
  if(opts.extra)ds.push(...opts.extra);
  return new Chart(document.getElementById(id),{type:'line',data:{labels:serie.map(p=>fdate(p.fecha)),datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:ds.length>1},tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${opts.pct?pf(c.parsed.y):uf(c.parsed.y)}`}}},
      scales:{y:{ticks:{callback:v=>opts.pct?v+' %':v+' u'},...(opts.y||{})}}}});
}
function constLine(n,v,label,color){return{label,data:Array(n).fill(v),borderColor:color,borderDash:[6,5],pointRadius:0,fill:false,borderWidth:2,type:'line'};}
function groupBar(id,groups,opts={}){
  const g=groups.filter(x=>x.resueltas>0);
  const colors=g.map(x=>x.vigilancia?AMBER:(x.pct>=(opts.breakeven||0)?NEON:'#c2453f'));
  const ds=[{label:'% acierto',data:g.map(x=>x.pct),backgroundColor:colors,borderRadius:6,type:'bar'}];
  if(opts.breakeven)ds.push(constLine(g.length,opts.breakeven,`Equilibrio ${nf(opts.breakeven,1)} %`,RED));
  return new Chart(document.getElementById(id),{type:'bar',data:{labels:g.map(x=>(x.vigilancia?'⚠ ':'')+x.grupo.replace('Liga Profesional Argentina','Liga Prof. Argentina')+` (${x.resueltas})`),datasets:ds},
    options:{indexAxis:opts.horizontal?'y':'x',responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:!!opts.breakeven},tooltip:{callbacks:{label:c=>{if(c.datasetIndex)return c.dataset.label;const x=g[c.dataIndex];return `${pf(x.pct)} · ${x.aciertos}/${x.resueltas} · ${uf(x.unidades)}${x.vigilancia?' · en vigilancia':''}`;}}}},
      scales:{[opts.horizontal?'x':'y']:{min:0,max:100,ticks:{callback:v=>v+' %'}}}}});
}
function groupTable(el,groups,label){
  el.innerHTML=`<table><thead><tr><th>${label}</th><th>Resueltas</th><th>Aciertos</th><th>Errores</th><th>%</th><th>Unidades</th></tr></thead><tbody>`+
    groups.map(g=>`<tr><td>${esc(g.grupo)}${g.vigilancia?' <span class="tag amber">en vigilancia</span>':''}</td><td>${g.resueltas}</td><td>${g.aciertos}</td><td>${g.errores}</td><td>${pf(g.pct)}</td><td class="${g.unidades<0?'ko':'ok'}">${uf(g.unidades)}</td></tr>`).join('')+'</tbody></table>';
}
const resTag=r=>({nulo:'<span class="tag grey">NULO</span>',acierto:'<span class="tag">ACIERTO</span>',error:'<span class="tag red">ERROR</span>',pendiente:'<span class="tag amber">PENDIENTE</span>',anulado:'<span class="tag grey">ANULADO</span>',sin_dato:'<span class="tag grey">SIN DATO</span>'}[r]||esc(r));

/* Tabla filtrable y ordenable */
function dataTable(root,rows,cols,filters){
  const st={q:'',f:{},sort:null,dir:1};
  root.innerHTML=`<div class="filters"><input type="search" placeholder="Buscar partido, liga…" aria-label="Buscar">${
    filters.map(f=>`<select data-k="${f.key}" aria-label="${f.label}"><option value="">${f.label}: todos</option>${[...new Set(rows.map(r=>String(f.get?f.get(r):r[f.key])))].sort().map(v=>`<option>${esc(v)}</option>`).join('')}</select>`).join('')
  }<span class="muted small" data-count></span></div><div class="tablewrap"><table><thead><tr>${cols.map((c,i)=>`<th data-i="${i}">${c.label}</th>`).join('')}</tr></thead><tbody></tbody></table></div>`;
  const tb=root.querySelector('tbody'),cnt=root.querySelector('[data-count]');
  const draw=()=>{let r=rows.filter(x=>{if(st.q&&!JSON.stringify(Object.values(x)).toLowerCase().includes(st.q))return false;
      return filters.every(f=>!st.f[f.key]||String(f.get?f.get(x):x[f.key])===st.f[f.key]);});
    if(st.sort!=null){const c=cols[st.sort],k=c.sort||(x=>x[c.key]);r=[...r].sort((a,b)=>{const A=k(a),B=k(b);return (A>B?1:A<B?-1:0)*st.dir;});}
    tb.innerHTML=r.map(x=>`<tr>${cols.map(c=>`<td>${c.fmt?c.fmt(x):esc(x[c.key])}</td>`).join('')}</tr>`).join('');
    cnt.textContent=`${r.length} de ${rows.length} filas`;};
  root.querySelector('input').addEventListener('input',e=>{st.q=e.target.value.toLowerCase();draw();});
  root.querySelectorAll('select').forEach(s=>s.addEventListener('change',e=>{st.f[s.dataset.k]=s.value;draw();}));
  root.querySelectorAll('th').forEach(th=>th.addEventListener('click',()=>{const i=+th.dataset.i;st.dir=st.sort===i?-st.dir:1;st.sort=i;
    root.querySelectorAll('th').forEach(t=>t.classList.remove('sorted-asc','sorted-desc'));th.classList.add(st.dir>0?'sorted-asc':'sorted-desc');draw();}));
  draw();
}
function stamp(d){const el=$('#generado');if(el)el.textContent=lStamp(d.generado_iso,d.generado);}
function fail(e){console.error(e);document.querySelectorAll('[data-needs-data]').forEach(x=>x.innerHTML=`<div class="notice">No se pudieron cargar los datos (${esc(e.message)}). Si abres el archivo directamente, sírvelo con <code>python3 -m http.server</code>.</div>`);}

/* ---------- Portada ---------- */
async function pageHome(){
  const d=await getJSON('data/resumen.json');stamp(d);
  const links={over_corners:'picksters-over-corners.html',parley_picks:'parley-picks.html'};
  $('#botcards').innerHTML=d.bots.map(b=>{if(b.pendiente)return`<div class="card"><h3>${esc(b.nombre)}</h3><p class="notice">Datos pendientes.</p></div>`;
    const s=b.resumen;return`<div class="card botcard"><h3>${esc(b.nombre)}</h3><div class="muted small">${esc(b.mercado)} · del ${fdate(b.desde)} al ${fdate(b.hasta)}</div>
    <div class="kpis"><div class="kpi"><div class="v">${s.resueltas}</div><div class="l">Resueltas</div></div><div class="kpi"><div class="v">${s.aciertos}</div><div class="l">Aciertos</div></div>
    <div class="kpi"><div class="v">${pf(s.pct)}</div><div class="l">% acierto</div></div><div class="kpi"><div class="v${s.unidades<0?' neg':''}">${uf(s.unidades)}</div><div class="l">Unidades</div></div></div>
    <a class="btn" href="${links[b.bot]}">Ver cómo trabaja →</a></div>`;}).join('');
  const bots=d.bots.filter(b=>!b.pendiente),cols=[NEON,BLUE,AMBER];
  const T=bots.reduce((a,b)=>({r:a.r+b.resumen.resueltas,a:a.a+b.resumen.aciertos,u:a.u+(b.resumen.unidades||0),p:a.p+(b.resumen.pendientes||0)}),{r:0,a:0,u:0,p:0});
  const tEl=$('#totales');if(tEl)kpis(tEl,{resueltas:T.r,aciertos:T.a,errores:T.r-T.a,pct:T.r?100*T.a/T.r:null,unidades:Math.round(T.u*100)/100,roi:T.r?100*T.u/T.r:null,pendientes:T.p});
  const dates=[...new Set(bots.flatMap(b=>b.serie.map(p=>p.fecha)))].sort();
  const mk=key=>bots.map((b,i)=>{const m=Object.fromEntries(b.serie.map(p=>[p.fecha,p[key]]));let last=null;
    return{label:b.nombre,data:dates.map(x=>m[x]!==undefined?(last=m[x]):last),borderColor:cols[i],backgroundColor:cols[i]+'22',tension:.25,pointRadius:2,spanGaps:true};});
  const base=(id,ds,pct)=>new Chart(document.getElementById(id),{type:'line',data:{labels:dates.map(fdate),datasets:ds},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    plugins:{tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${pct?pf(c.parsed.y):uf(c.parsed.y)}`}}},scales:{y:{ticks:{callback:v=>pct?v+' %':v+' u'}}}}});
  base('cmpUnits',mk('acum_unidades'),false);base('cmpPct',mk('acum_pct'),true);
}

/* ---------- Picksters Over Córners ---------- */
async function pageOver(){
  const d=await getJSON('data/over_corners.json');stamp(d);
  if(d.pendiente){document.querySelectorAll('[data-needs-data]').forEach(x=>x.innerHTML='<div class="notice">Datos pendientes: aún no llega el CSV del bot.</div>');return;}
  kpis($('#kpis'),d.resumen,[['Anulados',d.resumen.anulados],['Cuota media',nf(d.resumen.cuota_media,2)]]);
  $('#pendTxt').textContent=d.pendientes_lista.length?'Pendientes: '+d.pendientes_lista.join(' · '):'';
  lineChart('pctChart',d.serie,'acum_pct','% acumulado',NEON,{pct:true,fill:false,y:{min:0,max:100},extra:[constLine(d.serie.length,d.breakeven,'Equilibrio 62,5 % (cuota 1,60)',RED)]});
  lineChart('uChart',d.serie,'acum_unidades','Unidades acumuladas',NEON,{extra:[constLine(d.serie.length,0,'Cero',MUTED)]});
  groupBar('ligaChart',d.por_liga,{horizontal:true,breakeven:d.breakeven});groupTable($('#ligaTbl'),d.por_liga,'Competencia');
  groupBar('favChart',d.por_favorito.map(x=>({...x,grupo:'Favorito muy claro: '+x.grupo})),{breakeven:d.breakeven});groupTable($('#favTbl'),d.por_favorito,'¿Favorito muy claro?');
  dataTable($('#tabla'),d.picks,[
    {label:'Fecha (tu hora)',key:'fecha',sort:p=>p.iso||p.fecha,fmt:p=>esc(p.iso?lFechaHora(p.iso):p.fecha)},{label:'Partido',key:'partido'},
    {label:'Competencia',key:'competencia',fmt:p=>esc(p.competencia)+(p.vigilancia?' <span class="tag amber">vigilancia</span>':'')},
    {label:'Promedio',key:'promedio'},{label:'Córners',key:'corners',sort:p=>p.corners_total??-1},{label:'Cuota',key:'cuota',fmt:p=>nf(p.cuota,2)+(p.cuota_estimada?' <span class="muted small">(prom.)</span>':'')},
    {label:'Resultado',key:'resultado',fmt:p=>resTag(p.resultado)},{label:'Unid.',key:'unidades',sort:p=>p.unidades??-99,fmt:p=>p.unidades==null?'—':`<span class="${p.unidades<0?'ko':'ok'}">${uf(p.unidades)}</span>`},
    {label:'Fav. claro',key:'favorito_claro'}],
    [{key:'resultado',label:'Resultado'},{key:'competencia',label:'Competencia'},{key:'favorito_claro',label:'Favorito claro'}]);
}


/* ---------- Parley Picks ---------- */
const TIPO_PARLEY={principal:'Principal',conservador:'Conservador',conservador_alt:'Conservador alternativo'};
async function pageParley(){
  const d=await getJSON('data/parley_picks.json');stamp(d);
  if(d.pendiente){document.querySelectorAll('[data-needs-data]').forEach(x=>x.innerHTML='<div class="notice">Datos pendientes: aún no llega el registro del bot.</div>');return;}
  kpis($('#kpis'),d.resumen,[['Con cuota combinada',d.resumen.con_cuota],['Sin cuota combinada',d.resumen.sin_cuota],['Cuota media',nf(d.resumen.cuota_media,2)]]);
  const avisos=[];
  if(d.resumen.sin_cuota)avisos.push(`${d.resumen.sin_cuota} parley${d.resumen.sin_cuota===1?'':'s'} resuelto${d.resumen.sin_cuota===1?'':'s'} no entra${d.resumen.sin_cuota===1?'':'n'} en las unidades porque el registro no trae la cuota combinada. El resultado sí cuenta en el % de acierto.`);
  if(d.pendientes_lista.length)avisos.push('Pendientes: '+d.pendientes_lista.join(' · '));
  $('#pendTxt').innerHTML=avisos.map(esc).join(' ');
  if(d.serie.length){
    lineChart('pctChart',d.serie,'acum_pct','% acumulado',NEON,{pct:true,fill:false,y:{min:0,max:100}});
    lineChart('uChart',d.serie,'acum_unidades','Unidades acumuladas (solo parleys con cuota combinada)',NEON,{extra:[constLine(d.serie.length,0,'Cero',MUTED)]});
  }
  const tipos=d.por_tipo.map(x=>({...x,grupo:TIPO_PARLEY[x.grupo]||x.grupo}));
  groupBar('tipoChart',tipos,{});groupTable($('#tipoTbl'),tipos,'Tipo');
  groupBar('mktChart',d.por_mercado,{horizontal:true});groupTable($('#mktTbl'),d.por_mercado,'Mercado');
  const rs=d.resumen_selecciones;
  $('#selTxt').innerHTML=`De las selecciones sueltas (no se apuestan aparte, no suman unidades): <b>${rs.aciertos}/${rs.resueltas}</b> (${pf(rs.pct)}).`;
  if(d.avisos.length){$('#avisos').className='notice small';$('#avisos').innerHTML='<b>Notas del cálculo:</b><ul>'+d.avisos.map(a=>`<li>${esc(a)}</li>`).join('')+'</ul>';}
  const legs=p=>p.selecciones.map(s=>`${esc(s.partido)}: ${esc(s.seleccion)}${s.resultado_partido?` (${esc(s.resultado_partido)})`:''}`).join('<br>');
  dataTable($('#tabla'),d.picks,[
    {label:'Fecha',key:'fecha',sort:p=>p.iso||p.fecha,fmt:p=>esc(p.iso?lFechaHora(p.iso):fdate(p.fecha))},
    {label:'Parley',key:'parley',fmt:p=>`${esc(p.parley)} · ${esc(TIPO_PARLEY[p.tipo]||p.tipo_nombre)}`},
    {label:'Selecciones',key:'partido',fmt:p=>legs(p)},
    {label:'Competencias',key:'competencia'},
    {label:'Cuota comb.',key:'cuota',fmt:p=>p.cuota==null?'<span class="muted">no registrada</span>':nf(p.cuota,2)},
    {label:'Resultado',key:'resultado',fmt:p=>resTag(p.resultado)},
    {label:'Unid.',key:'unidades',sort:p=>p.unidades??-99,fmt:p=>p.unidades==null?'—':`<span class="${p.unidades<0?'ko':'ok'}">${uf(p.unidades)}</span>`}],
    [{key:'resultado',label:'Resultado'},{key:'tipo',label:'Tipo',get:p=>TIPO_PARLEY[p.tipo]||p.tipo}]);
}

/* ---------- Picks del día ---------- */
const DIAS=['dom','lun','mar','mié','jue','vie','sáb'];
const fday=d=>{const[y,m,dd]=d.split('-').map(Number);return DIAS[new Date(y,m-1,dd).getDay()]+' '+fdate(d);};
function marcaTag(m){const c={'ajustada':'amber','en vigilancia':'amber','favorito claro':'red','favorito moderado':'grey','principal':'','conservador':'grey','conservador alternativo':'grey'}[m]??'grey';
  return `<span class="tag ${c}">${esc(m==='C2'?'media C2':m)}</span>`;}
function whyBlock(a){if(!a)return'';const src={bot:'Argumento del bot',datos:'Resumen armado solo con los datos del registro',pendiente:''}[a.origen]||'';
  return `<div class="why"><div class="wt">💬 Por qué esta pick</div><p class="${a.origen==='pendiente'?'muted':''}">${esc(a.texto)}</p>${a.detalle?`<details><summary>Más detalle</summary><p>${esc(a.detalle)}</p></details>`:''}${src?`<div class="src">${src}</div>`:''}</div>`;}
async function pagePdd(){
  const d=await getJSON('data/picks_del_dia.json');stamp(d);$('#pddGen').textContent=lStamp(d.generado_iso,d.generado);
  const hoyL=lDay(new Date().toISOString()),manL=lDay(new Date(Date.now()+864e5).toISOString()),now=Date.now();
  const diaTxt=p=>{const k=p.iso?lDay(p.iso):p.fecha;return k===hoyL?'hoy':k===manL?'mañana':fday(k);};
  const empezo=p=>p.iso?Date.parse(p.iso)<=now:p.ya_empezo;
  const legs=p=>p.selecciones?`<ul class="legs">${p.selecciones.map(s=>`<li><b>${esc(s.partido)}</b> · ${esc(s.competencia)} · ${esc(s.seleccion)} <span class="muted">(${esc(s.mercado)})</span>${s.cuota!=null?` · cuota ${nf(s.cuota,2)}`:''}${s.hora&&!p.iso?` · ${esc(s.hora)}`:''}${s.iso?` · ${esc(lHora(s.iso))}`:''}${s.resultado_partido?` · ${esc(s.resultado_partido)}`:''}${s.estado&&s.estado!=='pendiente'?' '+resTag(s.estado):''}</li>`).join('')}</ul>`:'';
  const pickCard=p=>`<div class="pick"><div class="row1"><span class="hora">${esc(p.iso?lHora(p.iso):(p.hora||'—'))}</span><span class="zona">${esc(p.iso?zoneShort(p.iso):'')}</span><span class="fecha">${esc(diaTxt(p))}</span>${empezo(p)?'<span class="tag amber">en juego / por cerrar</span>':''}</div>
      <div class="partido">${esc(p.partido)}</div><div class="comp">${esc(p.competencia)}</div>${legs(p)}
      <div class="meta"><span>📊 <b>${esc(p.respaldo)}</b></span><span>💰 ${p.selecciones?'Cuota combinada':'Cuota'}: <b>${esc(p.cuota)}</b></span></div>
      ${p.marcas.length?`<div style="margin-top:6px">${p.marcas.map(marcaTag).join('')}</div>`:''}${whyBlock(p.argumento)}</div>`;
  $('#pddBots').innerHTML=d.bots.map(b=>{
    const list=b.pendientes.length?b.pendientes.map(pickCard).join(''):`<div class="empty">Hoy no hay picks de este bot (todavía).</div>`;
    return `<div class="card pdd-bot"><h3>${esc(b.nombre)}</h3><div class="mk">Mercado: ${esc(b.mercado)} · ${b.pendientes.length} pick${b.pendientes.length===1?'':'s'} abierta${b.pendientes.length===1?'':'s'}</div>${list}
      <a class="btn" href="${b.link}" style="margin-top:6px">Cómo trabaja este bot →</a></div>`;}).join('');
  $('#pddAyer').textContent='· '+fday(d.ayer);
  const resRow=p=>`<div class="pick res"><div><div class="partido">${esc(p.partido)}</div><div class="comp">${esc(p.competencia)}${p.selecciones?'':` · ${esc(p.iso?lHoraZ(p.iso):p.hora)}`}${p.detalle?' · '+esc(p.detalle):''}${p.nivel?' · '+esc(p.nivel):''}</div>${p.selecciones?`<div class="comp">${p.selecciones.map(s=>`${esc(s.partido)}: ${esc(s.seleccion)}${s.resultado_partido?` (${esc(s.resultado_partido)})`:''}`).join(' · ')}</div>`:''}${p.selecciones?`<div class="comp">Cuota combinada: ${esc(p.cuota)}</div>`:''}</div><div>${resTag(p.resultado)}</div></div>`;
  $('#pddRes').innerHTML=d.bots.map(b=>{
    const a=b.ayer.filter(p=>p.resultado==='acierto').length,e=b.ayer.filter(p=>p.resultado==='error').length;
    return `<div class="card"><h3>${esc(b.nombre)}</h3>${b.ayer.length?`<div class="mk muted small">${a} acierto${a===1?'':'s'} · ${e} error${e===1?'':'es'}</div>`+b.ayer.map(resRow).join(''):'<div class="empty">Ayer no hubo picks cerradas de este bot.</div>'}
    ${b.hoy_cerradas.length?`<h3 style="font-size:.95rem">Ya cerradas hoy</h3>`+b.hoy_cerradas.map(resRow).join(''):''}</div>`;}).join('');
}

/* ---------- Menú móvil ---------- */
function setupMenu(){const b=document.querySelector('.navbtn'),n=document.getElementById('menu');if(!b||!n)return;
  const set=o=>{n.classList.toggle('open',o);b.setAttribute('aria-expanded',String(o));b.setAttribute('aria-label',o?'Cerrar menú':'Abrir menú');b.firstElementChild.textContent=o?'✕':'☰';};
  b.addEventListener('click',()=>set(b.getAttribute('aria-expanded')!=='true'));
  n.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>set(false)));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&b.getAttribute('aria-expanded')==='true'){set(false);b.focus();}});
  matchMedia('(min-width:821px)').addEventListener('change',e=>{if(e.matches)set(false);});}

/* ---------- Fondos: carga perezosa y cambio suave a lo largo del scroll ---------- */
function setupFondos(){const ls=[...document.querySelectorAll('.bgfx .bgl')];if(ls.length<2)return;let cur=0,raf=0;
  const load=l=>{if(l.dataset.src){l.style.backgroundImage=`url('${l.dataset.src}')`;delete l.dataset.src;}};
  const upd=()=>{raf=0;const max=Math.max(1,document.documentElement.scrollHeight-innerHeight),f=scrollY/max;
    if(f>0.15)ls.forEach(load);
    const i=Math.min(ls.length-1,Math.floor(f*ls.length*0.999));
    if(i!==cur){load(ls[i]);ls[cur].classList.remove('on');ls[i].classList.add('on');cur=i;}};
  addEventListener('scroll',()=>{if(!raf)raf=requestAnimationFrame(upd);},{passive:true});upd();}
document.addEventListener('DOMContentLoaded',()=>{const p=document.body.dataset.page;setupMenu();setupFondos();localizeStatic();
  ({home:pageHome,over:pageOver,parley:pageParley,pdd:pagePdd,comunidad:async()=>stamp(await getJSON('data/resumen.json')),met:async()=>stamp(await getJSON('data/resumen.json'))}[p]||(async()=>{}))().catch(fail);});
