/* CórnersPicks — "En juego": partidos de las picks del día en tiempo real, con pitido y banderín en cada córner.
   Fuente configurable con <meta name="cp-live-src">:
     "espn"  → marcador público de ESPN directo desde el navegador (sin clave)
     URL     → JSON normalizado de un proxy/caché propio (p. ej. un Cloudflare Worker): {generado, fuente, partidos:[{id,liga,inicio,estado,minuto,local:{nombre,goles,corners},visita:{…}}]}
   ?demo=1 → SIMULACIÓN con partidos inventados (siempre rotulada como tal). */
(()=>{
const Q=new URLSearchParams(location.search),DEMO=Q.get('demo')==='1';
const SRC=(document.querySelector('meta[name="cp-live-src"]')||{}).content||'espn';
const POLL_LIVE=30e3,POLL_IDLE=5*60e3,PRE=15*60e3,POST=150*60e3,FX_MS=10e3;
const $=s=>document.querySelector(s);
const st={picks:[],partidos:{},prev:{},first:true,last:null,timer:0,log:[],fxT:0,err:null};

/* ---------- Sonido: pitido de árbitro sintetizado (WebAudio, sin archivos) ---------- */
let AC=null;const sndOn=()=>localStorage.getItem('cp_sonido')==='1';
function ctx(){if(!AC){const C=window.AudioContext||window.webkitAudioContext;if(!C)return null;AC=new C();}return AC;}
function unlock(){const c=ctx();if(c&&c.state==='suspended')c.resume();setTimeout(updSnd,50);}
function blast(c,t0,dur,vol){
  const o=c.createOscillator(),g=c.createGain(),lfo=c.createOscillator(),lg=c.createGain(),am=c.createGain(),ag=c.createGain();
  o.type='sine';o.frequency.value=2950;lfo.type='sine';lfo.frequency.value=27;          // trino de la bolita del silbato
  lg.gain.value=170;lfo.connect(lg);lg.connect(o.frequency);
  ag.gain.value=.35;lfo.connect(ag);ag.connect(am.gain);am.gain.value=.65;
  g.gain.setValueAtTime(0,t0);g.gain.linearRampToValueAtTime(vol,t0+.02);g.gain.setValueAtTime(vol,t0+dur-.06);g.gain.exponentialRampToValueAtTime(.0001,t0+dur);
  o.connect(am);am.connect(g);g.connect(c.destination);
  // soplo: ruido filtrado alrededor del tono
  const n=c.createBufferSource(),b=c.createBuffer(1,c.sampleRate*dur,c.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=Math.random()*2-1;
  n.buffer=b;const bp=c.createBiquadFilter();bp.type='bandpass';bp.frequency.value=3000;bp.Q.value=4;const ng=c.createGain();
  ng.gain.setValueAtTime(0,t0);ng.gain.linearRampToValueAtTime(vol*.35,t0+.02);ng.gain.exponentialRampToValueAtTime(.0001,t0+dur);
  n.connect(bp);bp.connect(ng);ng.connect(c.destination);
  [o,lfo,n].forEach(x=>{x.start(t0);x.stop(t0+dur+.05);});
}
function whistle(){if(!sndOn())return;const c=ctx();if(!c||c.state!=='running')return;const t=c.currentTime+.03;
  blast(c,t,.16,.22);blast(c,t+.24,.75,.25);if(navigator.vibrate)try{navigator.vibrate([120,80,400]);}catch(e){}}
function updSnd(){const b=$('#sndBtn'),on=sndOn();b.textContent=on?'🔇 Silenciar':'🔊 Activar sonido';b.setAttribute('aria-pressed',String(on));b.classList.toggle('on',on);
  $('#sndHint').hidden=!(on&&(!AC||AC.state!=='running'));}

/* ---------- Banderín (10 s) ---------- */
function showFx(a){const fx=$('#cornerFx');
  $('#fxTeam').textContent=a.equipo?`para ${a.equipo}`:'';
  $('#fxMatch').textContent=`${a.partido}${a.minuto?' · '+a.minuto:''}`;
  $('#fxCount').innerHTML=`🚩 Córners: <b>${a.cl} – ${a.cv}</b> · total <b>${a.cl+a.cv}</b>${a.n>1?` <span class="tag amber">+${a.n} desde la última lectura</span>`:''}`;
  $('#fxPick').innerHTML=a.picks.map(p=>`<span class="tag">${esc(p.bot)}</span> ${esc(p.estado)}`).join('<br>');
  fx.classList.toggle('sim',!!a.sim);fx.hidden=false;fx.classList.remove('go');void fx.offsetWidth;fx.classList.add('go');
  clearTimeout(st.fxT);st.fxT=setTimeout(()=>{fx.hidden=true;fx.classList.remove('go');},FX_MS);
  const card=document.getElementById('m-'+a.key);if(card){card.classList.remove('flash');void card.offsetWidth;card.classList.add('flash');}
  whistle();}

/* ---------- Picks del día → partidos a seguir ---------- */
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]/g,' ')
  .split(/\s+/).filter(w=>w&&!['fc','cf','sc','ac','cd','ca','club','de','la','el','the','afc','fk','sk','sv','ec','se','u'].includes(w));
function sameTeam(a,b){const A=norm(a),B=norm(b);if(!A.length||!B.length)return false;const ja=A.join(' '),jb=B.join(' ');
  if(ja===jb||ja.includes(jb)||jb.includes(ja))return true;return A.some(w=>w.length>=4&&B.some(v=>v===w||(v.length>=5&&w.length>=5&&(v.startsWith(w.slice(0,5))))));}
function linea(b,p){if(p.linea!=null&&p.senal)return{tipo:p.senal==='MENOS'?'menos':'mas',l:+String(p.linea).replace(',','.')};
  const m=/más de (\d+)[,.](\d)/i.exec(b.mercado||'');if(m&&!/minuto/i.test(b.mercado))return{tipo:'mas',l:+(m[1]+'.'+m[2])};
  if(/minuto 10|antes del minuto/i.test(b.mercado||''))return{tipo:'10min'};return null;}
function collectPicks(d){const out=[],today=lDay(new Date().toISOString());
  d.bots.forEach(b=>[...b.pendientes,...(b.hoy_cerradas||[])].forEach(p=>{if(!p.iso)return;
    const t=Date.parse(p.iso);if(isNaN(t))return;if(Date.now()-t>POST+6*3600e3)return;
    const [l,v]=String(p.partido).split(/\s+vs\.?\s+/i);
    out.push({bot:b.nombre,botId:b.bot,mercado:b.mercado,partido:p.partido,local:l,visita:v||'',iso:p.iso,t,comp:p.competencia,espn:p.espn_id||null,ln:linea(b,p),marcas:p.marcas||[]});}));
  return out.sort((a,b)=>a.t-b.t);}
const inWindow=p=>{const n=Date.now();return n>=p.t-PRE&&n<=p.t+POST;};

/* ---------- Fuente en vivo ---------- */
const ymd=iso=>iso.slice(0,10).replace(/-/g,'');
async function fetchESPN(dates){const res=[];
  for(const d of dates){const r=await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates=${d}`,{cache:'no-store'});
    if(!r.ok)throw new Error('ESPN '+r.status);const j=await r.json();
    (j.events||[]).forEach(e=>{const c=e.competitions&&e.competitions[0];if(!c)return;
      const side=h=>{const x=c.competitors.find(k=>k.homeAway===h)||{};const s=(x.statistics||[]).find(k=>k.name==='wonCorners');
        return{nombre:(x.team||{}).displayName||'',corto:(x.team||{}).shortDisplayName||'',goles:x.score!=null?+x.score:null,corners:s?+s.displayValue:null};};
      const ty=e.status.type||{};
      res.push({id:e.id,liga:(e.season||{}).slug||'',inicio:e.date,estado:ty.state,descanso:ty.name==='STATUS_HALFTIME',
        minuto:ty.state==='in'?(ty.name==='STATUS_HALFTIME'?'Descanso':(e.status.displayClock||'')):ty.state==='post'?'Final':'',local:side('home'),visita:side('away')});});}
  return{fuente:'ESPN (marcador público)',partidos:res};}
async function fetchProxy(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error('proxy '+r.status);return r.json();}

/* ---------- Simulación (?demo=1) ---------- */
const SIM={t0:Date.now(),m:[
  {id:'sim1',local:{nombre:'Atlético Demo',goles:0,corners:3},visita:{nombre:'Deportivo Prueba',goles:1,corners:2},min:52},
  {id:'sim2',local:{nombre:'Real Ejemplo',goles:0,corners:0},visita:{nombre:'Unión Ficticia',goles:0,corners:0},min:4},
  {id:'sim3',local:{nombre:'Sporting Simulado',goles:2,corners:6},visita:{nombre:'Racing Ensayo',goles:2,corners:4},min:78}]};
function simPicks(d){const b=Object.fromEntries(d.bots.map(x=>[x.bot,x]));const now=Date.now();
  const mk=(id,bot,i,mins)=>{const B=b[bot]||{nombre:bot,mercado:''},m=SIM.m[i];return{bot:B.nombre,botId:bot,mercado:B.mercado,partido:`${m.local.nombre} vs ${m.visita.nombre}`,local:m.local.nombre,visita:m.visita.nombre,
    iso:new Date(now-mins*60e3).toISOString(),t:now-mins*60e3,comp:'Liga de simulación',espn:id,ln:linea(B,{}),marcas:[],sim:true};};
  return[mk('sim1','over_corners',0,52),mk('sim2','corners_10min',1,4),mk('sim3','over_corners',2,78),
    {...mk('sim4','over_corners',0,-95),partido:'Equipo Uno Demo vs Equipo Dos Demo',local:'Equipo Uno Demo',visita:'Equipo Dos Demo',espn:'sim4'}];}
let simTick=0;
function fetchSim(){simTick++;const out=SIM.m.map((m,i)=>{m.min=Math.min(90,m.min+1);
    const plan={2:0,5:2,9:1};const hit=plan[simTick]===i||(simTick>9&&Math.random()<.1);
    if(hit){Math.random()<.55?m.local.corners++:m.visita.corners++;}
    return{id:m.id,liga:'simulación',inicio:new Date(Date.now()-m.min*60e3).toISOString(),estado:'in',minuto:m.min+"'",local:{...m.local},visita:{...m.visita}};});
  return Promise.resolve({fuente:'SIMULACIÓN',partidos:out});}

/* ---------- Emparejar picks ↔ partidos en vivo ---------- */
function match(p,list){if(p.espn){const x=list.find(e=>String(e.id)===String(p.espn));if(x)return{e:x,inv:false};}
  for(const e of list){const dt=Math.abs(Date.parse(e.inicio)-p.t);if(!isNaN(dt)&&dt>6*3600e3)continue;
    if(sameTeam(p.local,e.local.nombre)&&sameTeam(p.visita,e.visita.nombre))return{e,inv:false};
    if(sameTeam(p.local,e.visita.nombre)&&sameTeam(p.visita,e.local.nombre))return{e,inv:true};}
  return null;}
function pickEstado(p,tot,e){const ln=p.ln;if(!ln)return esc(p.mercado);
  if(ln.tipo==='10min'){const mi=e?parseInt(e.minuto,10):NaN;
    if(e&&(e.estado==='post'||e.descanso||mi>=10))return 'Al menos 1 córner antes del minuto 10 · ventana cerrada (el resultado lo confirma el bot)';
    return `Al menos 1 córner antes del minuto 10${tot!=null&&e&&e.estado==='in'?` · llevan ${tot}`:''}`;}
  const need=Math.floor(ln.l)+1;
  if(ln.tipo==='mas')return tot==null?`Más de ${nf(ln.l,1)} córners`:tot>ln.l?`Más de ${nf(ln.l,1)} · ✅ ya superó la línea (${tot})`:`Más de ${nf(ln.l,1)} · faltan <b>${need-tot}</b> (${tot} de ${need})`;
  return tot==null?`Menos de ${nf(ln.l,1)} córners`:`Menos de ${nf(ln.l,1)} · llevan ${tot}`;}

/* ---------- Pintar ---------- */
function render(){const live=[],next=[];const groups={};
  st.picks.forEach(p=>{const k=p.key||('p'+p.t+norm(p.partido).join(''));(groups[k]=groups[k]||{key:k,picks:[],m:p.m,p}).picks.push(p);});
  Object.values(groups).forEach(g=>{const e=g.m&&g.m.e;
    if(e&&(e.estado==='in'||(e.estado==='post'&&inWindow(g.p))))live.push(g);else if(e&&e.estado==='post')return;
    else if(inWindow(g.p))live.push(g);else if(g.p.t>Date.now())next.push(g);});
  $('#liveList').innerHTML=live.length?live.map(card).join(''):`<div class="empty">Ahora mismo no hay partidos de las picks en juego.${next.length?` El próximo empieza a las <b>${esc(lHoraZ(next[0].p.iso))}</b>.`:''}</div>`;
  $('#nextList').innerHTML=next.length?next.map(g=>`<div class="pick"><div class="row1"><span class="hora">${esc(lHora(g.p.iso))}</span><span class="zona">${esc(zoneShort(g.p.iso))}</span>${g.p.sim?'<span class="tag amber">SIMULACIÓN</span>':''}</div>
    <div class="partido">${esc(g.p.partido)}</div><div class="comp">${esc(g.p.comp)}</div><div style="margin-top:6px">${g.picks.map(p=>`<span class="tag">${esc(p.bot)}</span>`).join('')}</div></div>`).join(''):'<div class="empty">No hay más partidos de las picks hoy.</div>';
  const n=live.filter(g=>g.m&&g.m.e.estado==='in').length;
  $('#liveStat').innerHTML=st.err?`⚠️ No se pudo leer el marcador en vivo (${esc(st.err)}). Reintentando…`:
    `${n?`<span class="dot"></span> <b>${n}</b> en juego · `:''}${st.last?`Última lectura: <b>${esc(st.last.toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}))}</b> · cada ${anyLive()?'30 s':'5 min'}`:DEMO?'Simulación en marcha…':anyLive()?'Leyendo el marcador en vivo…':'Sin partidos en juego · la página se activa sola cuando empiece el próximo'}`;}
function card(g){const e=g.m&&g.m.e,inv=g.m&&g.m.inv,L=e?(inv?e.visita:e.local):null,V=e?(inv?e.local:e.visita):null;
  const tot=e&&L.corners!=null&&V.corners!=null?L.corners+V.corners:null;
  const est=!e?`<span class="tag grey">${Date.now()<g.p.t?'por empezar · '+esc(lHora(g.p.iso)):'sin datos en vivo'}</span>`:
    e.estado==='in'?`<span class="vivo">● ${e.descanso?'DESCANSO':'EN VIVO · '+esc(e.minuto)}</span>`:e.estado==='post'?'<span class="tag grey">FINAL</span>':`<span class="tag grey">por empezar · ${esc(lHora(g.p.iso))}</span>`;
  return `<div class="card match" id="m-${esc(g.key)}"><div class="row1">${est}${g.p.sim?'<span class="tag amber">SIMULACIÓN</span>':''}<span class="comp">${esc(g.p.comp)}</span></div>
   <div class="sb"><div class="tm">${esc(e?L.nombre:g.p.local)}</div><div class="sc">${e&&L.goles!=null?L.goles:'–'}<i>:</i>${e&&V.goles!=null?V.goles:'–'}</div><div class="tm r">${esc(e?V.nombre:g.p.visita)}</div></div>
   <div class="cn"><span class="cl">${e&&L.corners!=null?L.corners:'–'}</span><span class="ci">🚩 córners${tot!=null?` · total <b>${tot}</b>`:''}</span><span class="cl">${e&&V.corners!=null?V.corners:'–'}</span></div>
   ${e&&tot==null&&e.estado!=='pre'?'<div class="muted small">Esta liga no trae el conteo de córners en vivo en la fuente.</div>':''}
   ${!e&&inWindow(g.p)&&Date.now()>g.p.t?'<div class="muted small">No encontramos este partido en la fuente en vivo.</div>':''}
   <div class="pk">${g.picks.map(p=>{const pr=p.ln&&p.ln.tipo==='mas'&&tot!=null?Math.min(100,100*tot/(Math.floor(p.ln.l)+1)):null;
     return `<div class="pkr"><span class="tag">${esc(p.bot)}</span> ${pickEstado(p,tot,e)}${pr!=null?`<div class="prog"><i style="width:${pr}%"></i></div>`:''}</div>`;}).join('')}</div></div>`;}
function addLog(a){st.log.unshift(a);st.log=st.log.slice(0,15);
  $('#cornerLog').innerHTML=st.log.map(x=>`<div class="lg">🚩 <b>${esc(x.hora)}</b> · ${esc(x.minuto||'')} · ${esc(x.partido)} — córner${x.n>1?'s (+'+x.n+')':''} ${x.equipo?'para '+esc(x.equipo):''} · total ${x.cl+x.cv}${x.sim?' <span class="tag amber">SIMULACIÓN</span>':''}</div>`).join('');}

/* ---------- Ciclo ---------- */
const anyLive=()=>st.picks.some(p=>inWindow(p)&&!(p.m&&p.m.e.estado==='post'&&Date.now()-p.t>110*60e3));
async function tick(){clearTimeout(st.timer);
  try{if(DEMO||anyLive()){
      const dates=[...new Set(st.picks.filter(inWindow).map(p=>ymd(p.iso)))];
      const data=DEMO?await fetchSim():SRC==='espn'?await fetchESPN(dates):await fetchProxy(SRC);
      $('#srcName').textContent=data.fuente||'fuente pública';st.err=null;st.last=new Date();
      const L=data.partidos||[];
      st.picks.forEach(p=>{const m=match(p,L);p.m=m;p.key=m?'e'+m.e.id:null;});
      const seen=new Set();
      st.picks.forEach(p=>{if(!p.m||seen.has(p.key))return;seen.add(p.key);const e=p.m.e,inv=p.m.inv,Lh=inv?e.visita:e.local,Vh=inv?e.local:e.visita;
        if(Lh.corners==null||Vh.corners==null)return;const prev=st.prev[p.key];st.prev[p.key]={l:Lh.corners,v:Vh.corners};
        if(!prev||st.first&&!DEMO)return;const dl=Lh.corners-prev.l,dv=Vh.corners-prev.v;if(dl+dv<=0)return;
        const tot=Lh.corners+Vh.corners,ps=st.picks.filter(q=>q.key===p.key);
        const a={key:p.key,partido:`${Lh.nombre} vs ${Vh.nombre}`,equipo:dl>0&&dv<=0?Lh.nombre:dv>0&&dl<=0?Vh.nombre:'',n:dl+dv,cl:Lh.corners,cv:Vh.corners,minuto:e.minuto,sim:!!p.sim,
          hora:new Date().toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit',hourCycle:'h23'}),picks:ps.map(q=>({bot:q.bot,estado:pickEstado(q,tot,e).replace(/<[^>]+>/g,'')}))};
        addLog(a);showFx(a);});
      st.first=false;}
  }catch(err){console.error(err);st.err=err.message;}
  render();st.timer=setTimeout(tick,DEMO?7e3:anyLive()?POLL_LIVE:POLL_IDLE);}

async function init(){
  updSnd();
  $('#sndBtn').addEventListener('click',()=>{localStorage.setItem('cp_sonido',sndOn()?'0':'1');unlock();if(sndOn())setTimeout(whistle,80);});
  ['pointerdown','keydown'].forEach(ev=>document.addEventListener(ev,()=>{if(sndOn())unlock();},{passive:true}));
  $('#testBtn').addEventListener('click',()=>{unlock();setTimeout(()=>showFx({key:'',partido:'Prueba del aviso',equipo:'',n:1,cl:0,cv:1,minuto:'',sim:true,picks:[{bot:'Prueba',estado:'Así se verá cada córner (no es un partido real)'}]}),60);});
  $('#fxClose').addEventListener('click',()=>{clearTimeout(st.fxT);$('#cornerFx').hidden=true;});
  if(DEMO){$('#demoBanner').hidden=false;document.body.classList.add('is-demo');}
  const d=await getJSON('data/picks_del_dia.json');if(typeof stamp==='function')stamp(d);
  st.picks=DEMO?simPicks(d):collectPicks(d);
  render();tick();
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
}
document.addEventListener('DOMContentLoaded',()=>{if(document.body.dataset.page==='juego')init().catch(e=>{console.error(e);if(typeof fail==='function')fail(e);});});
})();
