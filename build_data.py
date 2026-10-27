#!/usr/bin/env python3
"""Convierte los CSV de ../site-data/ en los JSON que usa el sitio (site/data/).

Uso:  python3 build_data.py
Lee:  site-data/corners_10min.csv  (Bot Corners 10 Minutos)
      site-data/over_corners.csv   (Picksters Over Córners; opcional)
Escribe: data/corners_10min.json, data/over_corners.json, data/resumen.json, data/picks_del_dia.json
Antes copia /workspace/corners/picks_log.csv (archivo vivo del Bot Corners 10 Minutos)
a site-data/corners_10min.csv si existe y es más reciente.
"""
import csv, json, re, os, datetime
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, '..', 'site-data'))
OUT = os.path.join(HERE, 'data')
CUTOFF_10MIN = '2026-10-15'          # desde esta fecha la fuerte se toma a 1,70
VIGILANCIA_OVER = ['MLS', 'Liga Argentina']
BREAKEVEN_OVER = 62.5


def num(s):
    try:
        return float(str(s).strip().replace(',', '.'))
    except (ValueError, AttributeError):
        return None


# Nombres de casas de apuestas que NO se muestran en el sitio: uno por línea en site-data/casas_ocultas.txt
# (fuera del repo público, para que los nombres no aparezcan ni en el código publicado).
_casas_path = os.path.join(SRC, 'casas_ocultas.txt')
_casas = [l.strip() for l in open(_casas_path, encoding='utf-8')] if os.path.exists(_casas_path) else []
_casas = [r'\s+'.join(map(re.escape, c.split())) for c in _casas if c and not c.startswith('#')]
CASAS = re.compile(r'(?<![\w])(?:' + '|'.join(_casas) + r')(?![\w])', re.I) if _casas else None
NOTA_CUOTA = 'Como la cuota fluctúa en cada casa de apuestas, usamos una cuota promedio de 1,60 para calcular las unidades.'


def neutro(t):
    """Cambia cualquier nombre de casa de apuestas por un genérico."""
    return CASAS.sub('una casa de apuestas', t) if (CASAS and t) else (t or '')


def limpia_casa(t):
    """Quita las frases sobre la cuota leída en una casa concreta y neutraliza los nombres que queden."""
    if not t:
        return t
    # Frases tipo "Cuota <Casa> no consultada / no legible / leída ..." (se nombre o no la casa)
    t = re.sub(r'\s*Cuota\s+[A-ZÁÉÍÓÚ]\w+\s+(?:no\s+consultada|no\s+legible|le[ií]da)[^|]*?'
               r'(?:se usa 1[.,]60 estimada\.|sin iniciar sesi[oó]n\)[.;]?|;|\.(?=\s|$))', ' ', t)
    t = re.sub(r'(?:^|(?<=[.;]))\s*se usa 1[.,]60 estimada\.', ' ', t, flags=re.I)
    t = neutro(t)
    return re.sub(r'\s{2,}', ' ', t).strip()


def revisa_publicado():
    """El build falla si algún archivo publicado (repo + data/) nombra una casa de apuestas."""
    if not CASAS:
        print('AVISO: falta site-data/casas_ocultas.txt; no se revisan nombres de casas')
        return
    malos = []
    for raiz, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ('.git', 'screenshots', '__pycache__', 'venv', '.venv')]
        for fn in files:
            if fn.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp')):
                continue
            ruta = os.path.join(raiz, fn)
            try:
                txt = open(ruta, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            for m in CASAS.finditer(txt):
                malos.append(f"{os.path.relpath(ruta, HERE)}: «{m.group(0)}»")
    if malos:
        raise SystemExit('ERROR: el sitio nombra casas de apuestas:\n  ' + '\n  '.join(malos[:30]))


TZ_OFF = '-05:00'   # America/Bogota (sin horario de verano)


def iso(fecha, hora=None):
    """'2026-10-20' + '19:07' (o '2026-10-20 19:07') -> '2026-10-20T19:07:00-05:00'. None si no hay hora válida."""
    t = (fecha or '').strip() if hora is None else f"{(fecha or '').strip()} {(hora or '').strip()}"
    m = re.match(r'(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})', t)
    return f"{m.group(1)}T{int(m.group(2)):02d}:{m.group(3)}:00{TZ_OFF}" if m else None


def now_iso():
    return datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:00') + TZ_OFF


def r2(x):
    return round(x + 0.0, 2)


def stats(picks):
    """Métricas sobre picks ya normalizados (resultado acierto/error/otros)."""
    res = [p for p in picks if p['resultado'] in ('acierto', 'error')]
    a = sum(1 for p in res if p['resultado'] == 'acierto')
    u = sum(p['unidades'] for p in res if p['unidades'] is not None)
    n = len(res)
    cuotas = [p['cuota'] for p in res if p['cuota']]
    return {
        'resueltas': n, 'aciertos': a, 'errores': n - a,
        'pct': r2(100 * a / n) if n else None,
        'unidades': r2(u), 'roi': r2(100 * u / n) if n else None,
        'cuota_media': r2(sum(cuotas) / len(cuotas)) if cuotas else None,
        'total': len(picks),
        'pendientes': sum(1 for p in picks if p['resultado'] == 'pendiente'),
        'otros': sum(1 for p in picks if p['resultado'] not in ('acierto', 'error', 'pendiente')),
    }


def group(picks, key, order=None):
    g = defaultdict(list)
    for p in picks:
        g[p[key] or '—'].append(p)
    keys = order or sorted(g, key=lambda k: (-len([p for p in g[k] if p['resultado'] in ('acierto', 'error')]), k))
    return [dict(grupo=k, **stats(g[k])) for k in keys if k in g]


def series(picks):
    """Acumulado diario por fecha del partido."""
    days = defaultdict(list)
    for p in picks:
        if p['resultado'] in ('acierto', 'error'):
            days[p['fecha']].append(p)
    out, a, n, u = [], 0, 0, 0.0
    for d in sorted(days):
        da = sum(1 for p in days[d] if p['resultado'] == 'acierto')
        du = sum(p['unidades'] for p in days[d])
        a += da; n += len(days[d]); u += du
        out.append({'fecha': d, 'dia_picks': len(days[d]), 'dia_aciertos': da, 'dia_unidades': r2(du),
                    'acum_resueltas': n, 'acum_aciertos': a, 'acum_pct': r2(100 * a / n), 'acum_unidades': r2(u)})
    return out


LIVE_10MIN = '/workspace/corners/picks_log.csv'
LIVE_VIVO = '/workspace/corners/registro.csv'   # Cornes en Vivo (no confundir con picks_log.csv ni registro_corners.csv)
LIVE_ARGS_10MIN = '/workspace/corners/picks_argumentos.csv'   # opcional: fecha_reporte, partido, fecha_hora_bogota, argumento


def sync_10min():
    import shutil
    for live, name in ((LIVE_10MIN, 'corners_10min.csv'), (LIVE_ARGS_10MIN, 'corners_10min_argumentos.csv'),
                       (LIVE_VIVO, 'corners_vivo.csv')):
        dst = os.path.join(SRC, name)
        if os.path.exists(live) and (not os.path.exists(dst) or os.path.getmtime(live) > os.path.getmtime(dst)):
            shutil.copy2(live, dst)
            print('Copiado', live, '->', dst)


def load_args_10min():
    path = os.path.join(SRC, 'corners_10min_argumentos.csv')
    out = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding='utf-8')):
            k = ((r.get('partido') or '').strip().lower(), (r.get('fecha_hora_bogota') or '').strip())
            if (r.get('argumento') or '').strip():
                out[k] = neutro(r['argumento'].strip())
    return out


def build_10min():
    path = os.path.join(SRC, 'corners_10min.csv')
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    picks, avisos = [], []
    for r in rows:
        fecha = (r['fecha_hora_bogota'] or '')[:10]
        nivel = r['nivel'].strip().lower()
        res = r['resultado'].strip().lower()
        sin_apuesta = r['cuota_min'].strip().lower() == 'sin apuesta'
        # Cuota supuesta según la regla vigente
        if nivel == 'fuerte':
            regla = 1.65 if fecha < CUTOFF_10MIN else 1.70
            validas = (1.65, 1.70)
        else:
            regla, validas = 1.72, (1.72,)
        cm = num(r['cuota_min'])
        if cm is not None and cm in validas:
            cuota, origen = cm, 'cuota_min'
            if cm != regla:
                avisos.append(f"{r['partido']} ({fecha}): cuota_min {cm} distinta de la regla por fecha ({regla}); se usa cuota_min")
        else:
            cuota, origen = regla, 'regla'
        if res == 'acierto':
            u = cuota - 1
        elif res == 'error':
            u = -1.0
        else:
            u = None
        picks.append(OrderedDict(
            fecha=fecha, fecha_hora=r['fecha_hora_bogota'], iso=iso(r['fecha_hora_bogota']), fecha_reporte=r['fecha_reporte'],
            partido=r['partido'], competencia=r['competencia'], nivel=nivel,
            puntos=int(num(r['puntos'])) if num(r['puntos']) is not None else None,
            cuota=cuota, cuota_origen=origen, sin_apuesta=sin_apuesta,
            c2=r['c2'].strip().lower() == 'si', minuto=r['minuto_primer_corner'],
            resultado=res, unidades=r2(u) if u is not None else None,
            tipo=r['tipo'], fuente=r['fuente'], espn_id=r['espn_id']))
    picks_only = [p for p in picks if p['tipo'] == 'pick']
    s = stats(picks_only)
    apostadas = [p for p in picks_only if not p['sin_apuesta']]
    data = {
        'bot': 'corners_10min', 'nombre': 'Bot Corners 10 Minutos',
        'mercado': 'Al menos 1 córner antes del minuto 10 (0:00–9:59)',
        'generado': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'generado_iso': now_iso(),
        'fuente_csv': 'site-data/corners_10min.csv',
        'resumen': s,
        'resumen_solo_apostadas': stats(apostadas),
        'por_nivel': group(picks_only, 'nivel', ['fuerte', 'media']),
        'medias_c2': stats([p for p in picks_only if p['c2']]),
        'por_liga': group(picks_only, 'competencia'),
        'serie': series(picks_only),
        'serie_por_nivel': {n: series([p for p in picks_only if p['nivel'] == n]) for n in ('fuerte', 'media')},
        'referencias_excluidas': [p['partido'] for p in picks if p['tipo'] != 'pick'],
        'avisos': avisos,
        'picks': picks,
    }
    return data


def build_over():
    path = os.path.join(SRC, 'over_corners.csv')
    if not os.path.exists(path):
        return {'bot': 'over_corners', 'nombre': 'Picksters Over Córners', 'pendiente': True}
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    # La columna de cuota puede llamarse distinto en el CSV del bot; en la salida siempre es 'cuota'.
    cols = rows[0].keys() if rows else []
    CUOTA_COL = next((c for c in cols if c.strip().lower() == 'cuota'), None) or next((c for c in cols if 'cuota' in c.lower()), '')
    picks, avisos = [], []
    for r in rows:
        res = r['resultado'].strip().lower()
        cb = r.get(CUOTA_COL, '') or ''
        cuota = num(re.sub(r'[^\d.,]', '', cb.split()[0])) if cb.strip() else None
        estimada = (not cb.strip()) or ('estimad' in cb.lower())
        if cuota is None:
            cuota, estimada = 1.60, True
        u = num(r.get('unidades'))
        calc = (cuota - 1) if res == 'acierto' else (-1.0 if res == 'error' else (0.0 if res == 'anulado' else None))
        if u is None:
            u = calc
        elif calc is not None and abs(u - calc) > 0.005:
            avisos.append(f"{r['partido']} ({r['fecha']}): unidades del CSV {u} ≠ calculadas {calc:.2f}; se usa el CSV")
        notas = (r.get('notas') or '') + ' ' + (r.get('resumen') or '')
        m = re.search(r'[Ff]avorito muy claro:\s*(s[ií]|no)', notas)
        fav = ('sí' if m.group(1).lower().startswith('s') else 'no') if m else 'sin registro'
        cf = r.get('corners_final', '')
        mt = re.match(r'\s*(\d+)', cf or '')
        picks.append(OrderedDict(
            fecha=r['fecha'], hora=r['hora_bogota'], iso=iso(r['fecha'], r['hora_bogota']), partido=r['partido'], competencia=r['competicion'],
            promedio=r['promedio_filtro'], linea=r['linea'], corners=cf,
            corners_total=int(mt.group(1)) if mt else None,
            resultado=res, cuota=cuota, cuota_estimada=estimada,
            unidades=r2(u) if (u is not None and res in ('acierto', 'error', 'anulado')) else None,
            favorito_claro=fav, vigilancia=r['competicion'] in VIGILANCIA_OVER,
            resumen=limpia_casa(r['resumen']), notas=limpia_casa(r['notas'])))
    s = stats(picks)
    s['anulados'] = sum(1 for p in picks if p['resultado'] == 'anulado')
    liga = group(picks, 'competencia')
    for g in liga:
        g['vigilancia'] = g['grupo'] in VIGILANCIA_OVER
    return {
        'bot': 'over_corners', 'nombre': 'Picksters Over Córners',
        'mercado': 'Más de 9,5 córners totales en el partido',
        'generado': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'generado_iso': now_iso(),
        'fuente_csv': 'site-data/over_corners.csv',
        'breakeven': BREAKEVEN_OVER, 'vigilancia': VIGILANCIA_OVER,
        'resumen': s,
        'por_liga': liga,
        'por_favorito': group(picks, 'favorito_claro', ['sí', 'no', 'sin registro']),
        'serie': series(picks),
        'pendientes_lista': [p['partido'] for p in picks if p['resultado'] == 'pendiente'],
        'avisos': avisos,
        'picks': picks,
    }


# ---------------- Cornes en Vivo ----------------
CUOTA_VIVO = 1.90            # supuesta: el bot no guarda cuotas reales
BREAKEVEN_VIVO = round(100 / CUOTA_VIVO, 1)   # 52,6 %
def version_vivo(fecha, notas):
    m = re.match(r'\s*(v3-60|v3-HT)\b', notas or '', re.I)
    if m:
        return m.group(1).replace('ht', 'HT')
    return 'v3 (sin etiqueta)' if fecha >= '2026-10-17' else 'pre-v3'


def argumento_vivo(notas):
    """Argumento = notas del bot sin el código de versión ni lo que pasó después (Final/regrade)."""
    t = re.sub(r'^\s*v3-(60|HT)\s*;\s*', '', notas or '', flags=re.I)
    segs = [x.strip() for x in re.split(r';\s+', t) if x.strip()]
    pre, post = [], []
    for x in segs:
        (post if (post or re.match(r'(Final|regrade)\b', x, re.I)) else pre).append(x)
    pre = [neutro(x) for x in pre]
    texto = '; '.join(pre[:5]) + ('.' if pre else '')
    detalle = '; '.join(pre[5:])
    return {'texto': texto or 'Argumento pendiente.', 'detalle': detalle, 'origen': 'bot' if texto else 'pendiente',
            'despues': neutro('; '.join(post))}


def build_vivo():
    path = os.path.join(SRC, 'corners_vivo.csv')
    if not os.path.exists(path):
        return {'bot': 'corners_vivo', 'nombre': 'Cornes en Vivo', 'pendiente': True}
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    picks, avisos = [], []
    mapa = {'acierto': 'acierto', 'error': 'error', 'nulo': 'nulo', 'n/a': 'descartado', '': 'pendiente'}
    for r in rows:
        senal = (r['senal'] or '').strip().upper()
        senal = 'MÁS' if senal in ('MÁS', 'MAS') else ('MENOS' if senal == 'MENOS' else 'descartado')
        res = mapa.get((r['resultado'] or '').strip().lower(), (r['resultado'] or '').strip().lower())
        es_pick = senal in ('MÁS', 'MENOS')
        if es_pick and res == 'descartado':
            avisos.append(f"{r['partido']} ({r['fecha']}): señal {senal} con resultado N/A")
        if not es_pick and res in ('acierto', 'error', 'nulo'):
            avisos.append(f"{r['partido']} ({r['fecha']}): descartado con resultado {res}")
        u = (CUOTA_VIVO - 1) if res == 'acierto' else (-1.0 if res == 'error' else (0.0 if res == 'nulo' else None))
        minuto = (r['minuto'] or '').strip()
        ver = version_vivo(r['fecha'], r['notas'])
        picks.append(OrderedDict(
            fecha=r['fecha'], partido=r['partido'], competencia=r['competicion'],
            minuto=minuto, ht=minuto in ('45',) or 'descanso' in minuto.lower() or ver == 'v3-HT',
            marcador=r['marcador_60'], corners_lectura=r['corners_60'], proyeccion=num(r['proyeccion_ajustada']),
            linea=num(r['linea']), senal=senal, corners_finales=num(r['corners_finales']),
            resultado=res if es_pick else 'descartado', es_pick=es_pick, version=ver,
            familia='v3' if ver.startswith('v3') else 'pre-v3',
            cuota=CUOTA_VIVO if es_pick else None, cuota_estimada=True,
            unidades=r2(u) if (es_pick and u is not None) else None,
            argumento=argumento_vivo(r['notas']) if es_pick else None))
    sen = [p for p in picks if p['es_pick']]
    def st(ps):
        x = stats(ps); x['nulos'] = sum(1 for p in ps if p['resultado'] == 'nulo'); return x
    v3 = [p for p in sen if p['familia'] == 'v3']
    data = {
        'bot': 'corners_vivo', 'nombre': 'Cornes en Vivo',
        'mercado': 'Total de córners del partido MÁS o MENOS que la línea en vivo',
        'generado': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'generado_iso': now_iso(),
        'fuente_csv': 'site-data/corners_vivo.csv', 'cuota_supuesta': CUOTA_VIVO, 'breakeven': BREAKEVEN_VIVO,
        'resumen': st(sen),
        'lecturas': len(picks), 'descartados': len(picks) - len(sen),
        'senales': {'MÁS': sum(1 for p in sen if p['senal'] == 'MÁS'), 'MENOS': sum(1 for p in sen if p['senal'] == 'MENOS')},
        'resumen_v3': st(v3), 'resumen_pre_v3': st([p for p in sen if p['familia'] == 'pre-v3']),
        'por_familia': [dict(grupo=g, **st([p for p in sen if p['familia'] == g])) for g in ('v3', 'pre-v3')],
        'por_disparador_v3': [dict(grupo=g, **st([p for p in v3 if p['version'] == g])) for g in sorted({p['version'] for p in v3})],
        'por_senal_v3': [dict(grupo=g, **st([p for p in v3 if p['senal'] == g])) for g in ('MÁS', 'MENOS')],
        'por_senal_total': [dict(grupo=g, **st([p for p in sen if p['senal'] == g])) for g in ('MÁS', 'MENOS')],
        'v3_60_por_senal': [dict(grupo=g, **st([p for p in v3 if p['version'] == 'v3-60' and p['senal'] == g])) for g in ('MÁS', 'MENOS')],
        'por_liga': group(sen, 'competencia'),
        'serie': series(sen), 'serie_v3': series(v3),
        'avisos': avisos,
        'picks': picks,
    }
    return data


def _sort_key(p):
    return (p.get('fecha') or '') + ' ' + (p.get('hora') or '')


def build_picks_del_dia(b10, over, vivo=None):
    """Picks pendientes por bot + resultados de ayer (y de hoy ya cerrados). Solo datos de los CSV."""
    now = datetime.datetime.now()   # el reloj del equipo está en America/Bogota (UTC-5)
    hoy = now.strftime('%Y-%m-%d')
    ayer = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    ahora = now.strftime('%Y-%m-%d %H:%M')
    cerrados = ('acierto', 'error', 'anulado', 'sin_dato')
    args10 = load_args_10min()

    def arg10(p):
        a = args10.get((p['partido'].strip().lower(), (p['fecha_hora'] or '').strip()))
        if a:
            return {'texto': a, 'detalle': '', 'origen': 'bot'}
        if p['puntos'] is None:
            return {'texto': 'Argumento pendiente.', 'detalle': '', 'origen': 'pendiente'}
        t = f"Nivel {p['nivel']}: {p['puntos']} puntos en la escala del filtro (−3 a 8; fuerte desde 5, media con 4)."
        if p['c2']:
            t += ' Es una media C2 (la regla C, córners en contra del débil, sumó 2).'
        t += ' Sin apuesta: solo seguimiento.' if p['sin_apuesta'] else (' Cuota mínima para apostar: ' + f"{p['cuota']:.2f}".replace('.', ',') + '.')
        return {'texto': t, 'detalle': '', 'origen': 'datos'}

    def argOver(p):
        # El argumento del bot está en 'resumen'; 'notas' es interna y solo se usa para las marcas.
        res = (p.get('resumen') or '').strip()
        if not res:
            return {'texto': 'Argumento pendiente.', 'detalle': '', 'origen': 'pendiente'}
        t = f"Promedio combinado del filtro: {(p['promedio'] or '—').replace('.', ',')} córners (umbral: 10 o más de forma clara). " + res
        return {'texto': t.strip(), 'detalle': '', 'origen': 'bot'}

    def card10(p):
        hora = (p['fecha_hora'] or '')[11:16]
        marcas = [p['nivel']] + (['C2'] if p['c2'] else [])
        return OrderedDict(fecha=p['fecha'], hora=hora, iso=p['iso'], partido=p['partido'], competencia=p['competencia'],
                           nivel=p['nivel'], marcas=marcas,
                           respaldo=f"{p['puntos']} puntos" if p['puntos'] is not None else '—',
                           cuota='sin apuesta (solo seguimiento)' if p['sin_apuesta'] else 'mín. ' + f"{p['cuota']:.2f}".replace('.', ','),
                           sin_apuesta=p['sin_apuesta'], reportada=p['fecha_reporte'],
                           ya_empezo=(p['fecha'] + ' ' + hora) <= ahora,
                           resultado=p['resultado'], detalle=p['minuto'] or '', argumento=arg10(p))

    def cardOver(p):
        txt = ((p.get('resumen') or '') + ' ' + (p.get('notas') or '')).lower()
        marcas = []
        if 'ajustad' in txt or 'justo en el límite' in txt or 'justo encima' in txt:
            marcas.append('ajustada')
        if p['vigilancia']:
            marcas.append('en vigilancia')
        m = re.search(r'favorito muy claro:\s*(s[ií]|moderado)', txt)
        if m:
            marcas.append('favorito claro' if m.group(1).startswith('s') else 'favorito moderado')
        cuota = f"{p['cuota']:.2f}".replace('.', ',') + (' (promedio)' if p['cuota_estimada'] else '')
        return OrderedDict(fecha=p['fecha'], hora=p['hora'], iso=p['iso'], partido=p['partido'], competencia=p['competencia'],
                           nivel=None, marcas=marcas, respaldo='promedio ' + (p['promedio'] or '—').replace('.', ','),
                           cuota=cuota, sin_apuesta=False,
                           ya_empezo=(p['fecha'] + ' ' + (p['hora'] or '')) <= ahora,
                           resultado=p['resultado'], detalle=(f"{p['corners']} córners" if p['corners'] else ''), argumento=argOver(p))

    def cardVivo(p):
        marcas = [p['senal'], p['version'] if p['version'] != 'pre-v3' else 'pre-v3']
        if p['version'] == 'v3-HT':
            marcas.append('experimental')
        ln = '—' if p['linea'] is None else f"{p['linea']:.1f}".replace('.', ',')
        pr = '—' if p['proyeccion'] is None else f"{p['proyeccion']:.2f}".rstrip('0').rstrip(',.').replace('.', ',')
        cf = '' if p['corners_finales'] is None else f"{int(p['corners_finales'])} córners"
        return OrderedDict(fecha=p['fecha'], hora='', iso=None, vivo=True,
                           minuto=('descanso' if p['version'] == 'v3-HT' else (p['minuto'] + "'")),
                           partido=p['partido'], competencia=p['competencia'], nivel=None, marcas=marcas,
                           senal=p['senal'], linea=ln,
                           respaldo=f"{p['senal']} {ln} · proyección {pr}" + (f" · marcador {p['marcador']}, {p['corners_lectura']} córners" if p['marcador'] else ''),
                           cuota='1,90 (supuesta)', sin_apuesta=False, ya_empezo=True,
                           resultado=p['resultado'], detalle=cf, argumento=p['argumento'])

    bots = []
    specs = [(over, cardOver, 'Más de 9,5 córners totales', lambda p: True, 'picksters-over-corners.html'),
             (b10, card10, 'Al menos 1 córner antes del minuto 10 (0:00–9:59)', lambda p: p['tipo'] == 'pick', 'bot-10-minutos.html')]
    if vivo is not None:
        specs.append((vivo, cardVivo, 'Total de córners MÁS o MENOS que la línea en vivo', lambda p: p['es_pick'], 'cornes-en-vivo.html'))
    for b, fn, mercado, ok, link in specs:
        if b.get('pendiente'):
            bots.append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': mercado, 'link': link,
                         'pendientes': [], 'ayer': [], 'hoy_cerradas': [], 'sin_datos': True})
            continue
        def _eid(c, p):
            # id del partido en ESPN (si el registro del bot lo trae) para que la página En juego lo empareje exacto
            e = str(p.get('espn_id') or '').strip() if hasattr(p, 'get') else ''
            if e:
                c['espn_id'] = e
            return c
        ps = [_eid(fn(p), p) for p in b['picks'] if ok(p)]
        if b['bot'] == 'corners_vivo':
            # En vivo: se muestran las señales del día (con o sin resultado), no hay picks "por adelantado".
            bots.append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': mercado, 'link': link, 'vivo': True,
                         'pendientes': [p for p in ps if p['fecha'] == hoy],
                         'ayer': [p for p in ps if p['fecha'] == ayer and p['resultado'] in cerrados + ('nulo',)],
                         'hoy_cerradas': [], 'balance': b['resumen']})
            continue
        bots.append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': mercado, 'link': link,
                     'pendientes': sorted([p for p in ps if p['resultado'] == 'pendiente'], key=_sort_key),
                     'ayer': sorted([p for p in ps if p['fecha'] == ayer and p['resultado'] in cerrados], key=_sort_key),
                     'hoy_cerradas': sorted([p for p in ps if p['fecha'] == hoy and p['resultado'] in cerrados], key=_sort_key),
                     'balance': b['resumen']})
    return {'generado': ahora, 'generado_iso': now_iso(), 'zona_origen': 'America/Bogota (UTC-5)',
            'hoy': hoy, 'ayer': ayer, 'bots': bots}


def main():
    os.makedirs(OUT, exist_ok=True)
    sync_10min()
    bots = [build_10min(), build_over(), build_vivo()]
    for b in bots:
        with open(os.path.join(OUT, b['bot'] + '.json'), 'w', encoding='utf-8') as f:
            json.dump(b, f, ensure_ascii=False, indent=1)
    resumen = {'generado': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'generado_iso': now_iso(), 'bots': []}
    for b in bots:
        if b.get('pendiente'):
            resumen['bots'].append({'bot': b['bot'], 'nombre': b['nombre'], 'pendiente': True})
            continue
        resumen['bots'].append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': b['mercado'],
                                'resumen': b['resumen'], 'serie': b['serie'],
                                'desde': b['serie'][0]['fecha'] if b['serie'] else None,
                                'hasta': b['serie'][-1]['fecha'] if b['serie'] else None})
    with open(os.path.join(OUT, 'resumen.json'), 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    pdd = build_picks_del_dia(bots[0], bots[1], bots[2])
    with open(os.path.join(OUT, 'picks_del_dia.json'), 'w', encoding='utf-8') as f:
        json.dump(pdd, f, ensure_ascii=False, indent=1)
    revisa_publicado()
    for b in bots:
        s = b.get('resumen')
        if s:
            print(f"{b['nombre']}: {s['aciertos']}/{s['resueltas']} ({s['pct']} %), {s['unidades']:+.2f} u, "
                  f"pendientes {s['pendientes']}, otros {s['otros']}")
        for a in b.get('avisos', []):
            print('  aviso:', a)
        if b['bot'] == 'corners_10min':
            for n in b['por_nivel']:
                print(f"  {n['grupo']}: {n['aciertos']}/{n['resueltas']} ({n['pct']} %), {n['unidades']:+.2f} u")
            c = b['medias_c2']; print(f"  medias C2: {c['aciertos']}/{c['resueltas']}")
            sa = b['resumen_solo_apostadas']; print(f"  solo apostadas: {sa['aciertos']}/{sa['resueltas']} {sa['unidades']:+.2f} u")
        if b['bot'] == 'corners_vivo' and not b.get('pendiente'):
            print(f"  lecturas {b['lecturas']}, descartados {b['descartados']}, señales {b['senales']}, nulos {b['resumen']['nulos']}")
            for k in ('por_familia', 'por_disparador_v3', 'por_senal_v3', 'v3_60_por_senal'):
                print('  ' + k + ': ' + ', '.join(f"{g['grupo']} {g['aciertos']}-{g['errores']}-{g['nulos']} ({g['unidades']:+.2f} u)" for g in b[k]))
    print(f"\nPicks del día (generado {pdd['generado_iso']}):")
    for b in pdd['bots']:
        print(f"- {b['nombre']}: {len(b['pendientes'])} pendientes")
        for p in b['pendientes']:
            print(f"    {p['fecha']} {p['hora']}  {p['partido']} ({p['competencia']}) · {p['respaldo']} · cuota {p['cuota']} · {', '.join(p['marcas']) or '—'}")
            print(f"        por qué ({p['argumento']['origen']}): {p['argumento']['texto'][:160]}")
        print(f"  resultados de ayer ({pdd['ayer']}): " + (', '.join(f"{p['partido']} {p['resultado'].upper()}" for p in b['ayer']) or 'ninguno'))


if __name__ == '__main__':
    main()
