/* CórnersPicks · proxy/caché para la página "En juego" (Cloudflare Worker, plan gratis).
   NO está desplegado. Solo se usa si se decide no leer ESPN directo desde el navegador.
   - Lee las picks del día del sitio publicado y el marcador público de ESPN.
   - Guarda la respuesta 20 s en la caché de Cloudflare: sin importar cuántos visitantes haya,
     ESPN recibe como máximo ~3 consultas por minuto, y solo mientras haya un partido de las picks en ventana.
   - Responde el formato normalizado que entiende js/en-juego.js:
     {generado, fuente, partidos:[{id,liga,inicio,estado,descanso,minuto,local:{nombre,goles,corners},visita:{…}}]}
   Para usarlo: en en-juego.html cambiar <meta name="cp-live-src" content="espn"> por la URL del Worker. */
const SITE='https://wessesito.github.io/cornerspicks/data/picks_del_dia.json';
const ESPN='https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates=';
const UA='Mozilla/5.0 (compatible; CornersPicksLive/1.0; +https://wessesito.github.io/cornerspicks/)';
const CORS={'access-control-allow-origin':'*','content-type':'application/json; charset=utf-8'};
const PRE=15*60e3,POST=150*60e3;

async function cached(req,ctx,ttl,make){const cache=caches.default,key=new Request(req,{method:'GET'});
  let r=await cache.match(key);if(r)return r;
  r=new Response(JSON.stringify(await make()),{headers:{...CORS,'cache-control':`public, max-age=${ttl}`}});
  ctx.waitUntil(cache.put(key,r.clone()));return r;}

async function picks(){const r=await fetch(SITE,{cf:{cacheTtl:300,cacheEverything:true}});const d=await r.json();
  return d.bots.flatMap(b=>[...b.pendientes,...(b.hoy_cerradas||[])]).filter(p=>p.iso).map(p=>Date.parse(p.iso));}

async function live(){const now=Date.now(),ts=(await picks()).filter(t=>now>=t-PRE&&now<=t+POST);
  if(!ts.length)return{generado:new Date().toISOString(),fuente:'ESPN (marcador público) vía caché',partidos:[],nota:'sin partidos de las picks en ventana'};
  // fecha del partido en hora de Bogotá (UTC-5), igual que el navegador
  const dates=[...new Set(ts.map(t=>new Date(t-5*3600e3).toISOString().slice(0,10).replace(/-/g,'')))];
  const out=[];
  for(const d of dates){const r=await fetch(ESPN+d,{headers:{'user-agent':UA,accept:'application/json'}});if(!r.ok)throw new Error('ESPN '+r.status);
    const j=await r.json();
    for(const e of j.events||[]){const c=e.competitions?.[0];if(!c)continue;const t=Date.parse(e.date);
      if(!ts.some(x=>Math.abs(x-t)<6*3600e3))continue;                   // solo partidos cercanos a la hora de alguna pick
      const side=h=>{const x=c.competitors.find(k=>k.homeAway===h)||{},s=(x.statistics||[]).find(k=>k.name==='wonCorners');
        return{nombre:x.team?.displayName||'',goles:x.score!=null?+x.score:null,corners:s?+s.displayValue:null};};
      const ty=e.status?.type||{};
      out.push({id:e.id,liga:e.season?.slug||'',inicio:e.date,estado:ty.state,descanso:ty.name==='STATUS_HALFTIME',
        minuto:ty.state==='in'?(ty.name==='STATUS_HALFTIME'?'Descanso':e.status.displayClock||''):ty.state==='post'?'Final':'',local:side('home'),visita:side('away')});}}
  return{generado:new Date().toISOString(),fuente:'ESPN (marcador público) vía caché',partidos:out};}

export default{async fetch(req,env,ctx){
  if(req.method==='OPTIONS')return new Response(null,{headers:{...CORS,'access-control-allow-methods':'GET'}});
  try{return await cached(req,ctx,20,live);}
  catch(e){return new Response(JSON.stringify({error:String(e.message||e)}),{status:502,headers:CORS});}}};
