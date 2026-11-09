#!/usr/bin/env python3
"""Convierte los CSV de ../site-data/ en los JSON que usa el sitio (site/data/).

Uso:  python3 build_data.py
Lee:  site-data/over_corners.csv   (Picksters Over Córners)
      site-data/parley_picks.csv   (Parley Picks; se copia desde
      /workspace/parley_picks/registro_parleys.csv si es más reciente)
Escribe: data/over_corners.json, data/parley_picks.json,
         data/resumen.json, data/picks_del_dia.json
"""
import csv, json, re, os, datetime
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, '..', 'site-data'))
OUT = os.path.join(HERE, 'data')
VIGILANCIA_OVER = ['MLS', 'Liga Argentina']
BREAKEVEN_OVER = 62.5
LIVE_PARLEY = '/workspace/parley_picks/registro_parleys.csv'


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
# Una casa comparte nombre con la palabra del glosario (el tamaño de la apuesta).
# Solo se neutraliza en textos del registro de Parley Picks, no en el resto del sitio.
CASA_HOMONIMA = re.compile(r'(?<![\w])St' r'ake(?![\w])', re.I)


def neutro(t):
    """Cambia cualquier nombre de casa de apuestas por un genérico."""
    return CASAS.sub('una casa de apuestas', t) if (CASAS and t) else (t or '')


def limpia_casa(t):
    """Quita las frases sobre la cuota leída en una casa concreta y neutraliza los nombres que queden."""
    if not t:
        return t
    t = re.sub(r'\s*Cuota\s+[A-ZÁÉÍÓÚ]\w+\s+(?:no\s+consultada|no\s+legible|le[ií]da)[^|]*?'
               r'(?:se usa 1[.,]60 estimada\.|sin iniciar sesi[oó]n\)[.;]?|;|\.(?=\s|$))', ' ', t)
    t = re.sub(r'(?:^|(?<=[.;]))\s*se usa 1[.,]60 estimada\.', ' ', t, flags=re.I)
    t = neutro(t)
    return re.sub(r'\s{2,}', ' ', t).strip()


def limpia_parley(t):
    """Neutraliza casas (incluida esa casa) en textos del registro de Parley Picks."""
    if not t:
        return ''
    t = CASA_HOMONIMA.sub('una casa de apuestas', t)
    return limpia_casa(t)


def liga_limpia(t):
    """El nombre comercial de la liga colombiana incluye el de una casa; se muestra sin ese nombre."""
    return limpia_parley(re.sub(r'Liga\s+Bet' r'Play', 'Primera A Colombia', t or '', flags=re.I))


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
    con_u = [p for p in res if p['unidades'] is not None]
    u = sum(p['unidades'] for p in con_u)
    n = len(res)
    nu = len(con_u)
    cuotas = [p['cuota'] for p in res if p['cuota']]
    return {
        'resueltas': n, 'aciertos': a, 'errores': n - a,
        'pct': r2(100 * a / n) if n else None,
        'unidades': r2(u), 'roi': r2(100 * u / nu) if nu else None,
        'cuota_media': r2(sum(cuotas) / len(cuotas)) if cuotas else None,
        'total': len(picks),
        'pendientes': sum(1 for p in picks if p['resultado'] == 'pendiente'),
        'otros': sum(1 for p in picks if p['resultado'] not in ('acierto', 'error', 'pendiente')),
        'con_cuota': nu,
        'sin_cuota': n - nu,
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
        du = sum(p['unidades'] for p in days[d] if p['unidades'] is not None)
        a += da; n += len(days[d]); u += du
        out.append({'fecha': d, 'dia_picks': len(days[d]), 'dia_aciertos': da, 'dia_unidades': r2(du),
                    'acum_resueltas': n, 'acum_aciertos': a, 'acum_pct': r2(100 * a / n), 'acum_unidades': r2(u)})
    return out


def sync_fuentes():
    import shutil
    dst = os.path.join(SRC, 'parley_picks.csv')
    if os.path.exists(LIVE_PARLEY) and (not os.path.exists(dst) or os.path.getmtime(LIVE_PARLEY) > os.path.getmtime(dst)):
        shutil.copy2(LIVE_PARLEY, dst)
        print('Copiado', LIVE_PARLEY, '->', dst)


# ---------------- Picksters Over Córners ----------------
def build_over():
    path = os.path.join(SRC, 'over_corners.csv')
    if not os.path.exists(path):
        return {'bot': 'over_corners', 'nombre': 'Picksters Over Córners', 'pendiente': True}
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
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


# ---------------- Parley Picks ----------------
EST_PARLEY = {
    'ganado': 'acierto', 'ganada': 'acierto',
    'perdido': 'error', 'perdida': 'error',
    'pendiente': 'pendiente',
    'nulo': 'anulado', 'nula': 'anulado',
}
TIPO_LABEL = {
    'principal': 'principal',
    'conservador': 'conservador',
    'conservador_alt': 'conservador alternativo',
}
HORA_COT = re.compile(r'\b(\d{1,2}):(\d{2})\s*COT\b', re.I)


def razon_nota(t):
    """Quita de una nota ya limpia la hora, la fuente de la cuota y avisos técnicos; deja el argumento si lo hay."""
    s = t or ''
    for pat in (
        r'cuota total aprox.*',
        r'\b\d{1,2}:\d{2}\s*COT\b',
        r'una casa de apuestas(?:\s+internacional)?(?:\s+\([^)]*\))?',
        r'vía\s+\S+',
        r'(?:no verificada|no es casa de Wesley|no casa de Wesley|casa no identificada|casas de Wesley)[^;]*',
        r'promedio de mercado\s+\S+(?:\s+\([^)]*\))?',
        r'\d+\s*/\s*\d+\s+bookie[^;]*',
        r'cuota de comparador[^;]*',
        r'mejor cuota[^;]*',
        r'\(\s*mejor[^)]*\)',
        r'mejor\s+\d+[.,]\d+[^;]*',
        r'rango\s+\d+[.,]\d+\s*-\s*\d+[.,]\d+',
    ):
        s = re.sub(pat, ' ', s, flags=re.I)
    s = re.sub(r'\s*;\s*', ' · ', s)
    s = re.sub(r'[\s,]+', ' ', s).strip(' .;—-·')
    return s


def _solo_meta(t):
    return not razon_nota(t)


def _hora_de_nota(notas):
    m = HORA_COT.search(notas or '')
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def load_drive_parley():
    """Copia de la pestaña Parley Picks de Drive (site-data/parley_picks_drive.csv)."""
    path = os.path.join(SRC, 'parley_picks_drive.csv')
    if not os.path.exists(path):
        return {}
    out = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        key = ((r.get('fecha') or '').strip(), (r.get('parley') or '').strip())
        if key[0] and key[1]:
            out[key] = r
    return out


def cuota_desde_drive(drv):
    """Usa la cuota de Drive solo si las notas no dicen que no hay cuota total.

    El 4 nov la columna tiene 1,75 pero las notas dicen «Sin cuota total»; eso no se usa.
    El 27 oct las notas documentan que se usó el límite inferior del rango aproximado.
    """
    if not drv:
        return None, None, None
    cuota = num(drv.get('cuota'))
    notas = drv.get('notas') or ''
    if cuota is None:
        return None, None, notas
    if re.search(r'sin cuota total', notas, re.I):
        return None, 'drive_sin_cuota', notas
    if re.search(r'l[ií]mite inferior', notas, re.I):
        return cuota, 'drive_limite_inferior', notas
    return cuota, 'drive', notas


def build_parley():
    path = os.path.join(SRC, 'parley_picks.csv')
    if not os.path.exists(path):
        return {'bot': 'parley_picks', 'nombre': 'Parley Picks', 'pendiente': True}
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    grupos = OrderedDict()
    for r in rows:
        key = ((r.get('fecha') or '').strip(), (r.get('parley') or '').strip())
        grupos.setdefault(key, []).append(r)
    drive = load_drive_parley()
    if drive:
        print(f"Parley Picks: fusionando {len(drive)} filas de site-data/parley_picks_drive.csv")

    picks, avisos, sels_flat = [], [], []
    for key, drv in drive.items():
        if key not in grupos:
            avisos.append(f"{key[0]} {key[1]}: está en la hoja de Drive y no en el CSV del bot; no se añade (no se mezclan fuentes de selecciones)")
    for (fecha, pid), legs in grupos.items():
        tipo = (legs[0].get('tipo') or '').strip().lower()
        tipo_nom = TIPO_LABEL.get(tipo, tipo or 'parley')
        estado_raw = (legs[0].get('estado_parley') or '').strip().lower()
        res = EST_PARLEY.get(estado_raw, estado_raw or 'pendiente')
        # Cuota combinada: primero la columna del CSV del bot; si falta, la de Drive
        # solo cuando las notas de Drive no dicen «Sin cuota total». No se multiplica
        # cuotas individuales ni se inventa a partir de un rango, salvo el límite
        # inferior que la propia hoja documenta haber usado.
        cuotas_tot = []
        for r in legs:
            ct = num(r.get('cuota_total_parley'))
            if ct is not None:
                cuotas_tot.append(ct)
        cuota = cuotas_tot[0] if cuotas_tot else None
        cuota_origen = 'csv' if cuota is not None else None
        if len(set(cuotas_tot)) > 1:
            avisos.append(f"{fecha} {pid}: cuota_total_parley distinta entre filas ({cuotas_tot}); se usa {cuota}")
        drv = drive.get((fecha, pid))
        d_cuota, d_origen, d_notas = cuota_desde_drive(drv)
        if drv:
            d_res = EST_PARLEY.get((drv.get('estado') or '').strip().lower(), (drv.get('resultado') or '').strip().lower())
            if d_res in ('acierto', 'error') and res in ('acierto', 'error') and d_res != res:
                avisos.append(f"{fecha} {pid}: el CSV del bot dice {res} y Drive dice {d_res}; se mantiene el CSV")
        if cuota is not None and d_cuota is not None and abs(cuota - d_cuota) > 0.005:
            avisos.append(f"{fecha} {pid}: cuota del CSV {cuota} ≠ Drive {d_cuota}; se usa el CSV")
        if cuota is None and d_cuota is not None:
            cuota, cuota_origen = d_cuota, d_origen
            if d_origen == 'drive_limite_inferior':
                avisos.append(f"{fecha} {pid} ({tipo_nom}): sin cuota combinada en el CSV del bot; se usa {str(cuota).replace('.', ',')} de la hoja de Drive (límite inferior del rango aproximado que documenta esa hoja)")
            else:
                avisos.append(f"{fecha} {pid} ({tipo_nom}): sin cuota combinada en el CSV del bot; se usa {str(cuota).replace('.', ',')} de la hoja de Drive")
        elif cuota is None and d_origen == 'drive_sin_cuota':
            avisos.append(f"{fecha} {pid} ({tipo_nom}): la hoja de Drive tiene {str(num(drv.get('cuota'))).replace('.', ',')} en la columna de cuota, pero sus notas dicen que no hay cuota total; no se usa. El resultado cuenta en el % de acierto, no en las unidades")
        elif cuota is None and res in ('acierto', 'error'):
            avisos.append(f"{fecha} {pid} ({tipo_nom}): sin cuota combinada registrada; el resultado cuenta en el % de acierto, no en las unidades")

        stake = 1.0
        if drv and num(drv.get('stake')):
            stake = num(drv.get('stake'))
        if res == 'acierto' and cuota is not None:
            u = (cuota - 1) * stake
        elif res == 'error' and cuota is not None:
            u = -stake
        elif res == 'anulado' and cuota is not None:
            u = 0.0
        else:
            u = None

        selecciones = []
        for r in legs:
            notas_raw = r.get('notas') or ''
            hora = _hora_de_nota(notas_raw)
            notas = limpia_parley(notas_raw)
            est_sel = EST_PARLEY.get((r.get('estado_seleccion') or '').strip().lower(),
                                     (r.get('estado_seleccion') or '').strip().lower() or 'pendiente')
            sel = OrderedDict(
                partido=(r.get('partido') or '').strip(),
                competencia=liga_limpia(r.get('competicion')),
                seleccion=limpia_parley(r.get('seleccion')),
                mercado=(r.get('mercado') or '').strip(),
                cuota=num(r.get('cuota')),
                resultado_partido=(r.get('resultado_partido') or '').strip(),
                estado=est_sel,
                hora=hora,
                iso=iso(fecha, hora) if hora else None,
                notas=notas,
            )
            selecciones.append(sel)
            sels_flat.append(OrderedDict(
                fecha=fecha, resultado=est_sel, unidades=None, cuota=sel['cuota'],
                mercado=sel['mercado'] or '—', competencia=sel['competencia'] or '—',
            ))

        razones = []
        for s in selecciones:
            if s['notas'] and not _solo_meta(s['notas']):
                razones.append(f"{s['partido']}: {s['seleccion']} — {s['notas']}")
        if razones:
            argumento = {'texto': ' '.join(razones), 'detalle': '', 'origen': 'bot'}
        else:
            argumento = {'texto': 'Argumento pendiente.', 'detalle': '', 'origen': 'pendiente'}

        comps = []
        for s in selecciones:
            if s['competencia'] and s['competencia'] not in comps:
                comps.append(s['competencia'])
        n = len(selecciones)
        titulo = f"Parley {tipo_nom} ({pid}) · {n} {'selección' if n == 1 else 'selecciones'}"
        isos = [s['iso'] for s in selecciones if s['iso']]
        horas = [s['hora'] for s in selecciones if s['hora']]
        picks.append(OrderedDict(
            fecha=fecha,
            hora=min(horas) if horas else '',
            iso=min(isos) if isos else None,
            parley=pid,
            tipo=tipo,
            tipo_nombre=tipo_nom,
            partido=titulo,
            competencia=' · '.join(comps),
            n_selecciones=n,
            cuota=cuota,
            cuota_registrada=cuota is not None,
            cuota_origen=cuota_origen,
            resultado=res,
            unidades=r2(u) if u is not None else None,
            selecciones=selecciones,
            argumento=argumento,
        ))

    s = stats(picks)
    s_sel = stats(sels_flat)
    return {
        'bot': 'parley_picks', 'nombre': 'Parley Picks',
        'mercado': 'Parley diario de fútbol (3 a 4 selecciones): resultado, ambos marcan, doble oportunidad o total de goles',
        'generado': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'generado_iso': now_iso(),
        'fuente_csv': 'site-data/parley_picks.csv',
        'fuente_drive': 'site-data/parley_picks_drive.csv' if drive else None,
        'resumen': s,
        'resumen_selecciones': s_sel,
        'por_tipo': group(picks, 'tipo', ['principal', 'conservador', 'conservador_alt']),
        'por_mercado': group(sels_flat, 'mercado'),
        'serie': series(picks),
        'pendientes_lista': [p['partido'] for p in picks if p['resultado'] == 'pendiente'],
        'avisos': avisos,
        'picks': picks,
    }


def _sort_key(p):
    return (p.get('fecha') or '') + ' ' + (p.get('hora') or '')


def build_picks_del_dia(over, parley):
    """Picks pendientes por bot + resultados de ayer (y de hoy ya cerrados). Solo datos de los CSV."""
    now = datetime.datetime.now()   # el reloj del equipo está en America/Bogota (UTC-5)
    hoy = now.strftime('%Y-%m-%d')
    ayer = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    ahora = now.strftime('%Y-%m-%d %H:%M')
    cerrados = ('acierto', 'error', 'anulado', 'sin_dato')

    def argOver(p):
        res = (p.get('resumen') or '').strip()
        if not res:
            return {'texto': 'Argumento pendiente.', 'detalle': '', 'origen': 'pendiente'}
        t = f"Promedio combinado del filtro: {(p['promedio'] or '—').replace('.', ',')} córners (umbral: 10 o más de forma clara). " + res
        return {'texto': t.strip(), 'detalle': '', 'origen': 'bot'}

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

    def cardParley(p):
        marcas = [p['tipo_nombre']]
        if p['cuota'] is not None:
            cuota = f"{p['cuota']:.2f}".replace('.', ',')
        else:
            cuota = 'cuota combinada no registrada'
        hora = p.get('hora') or ''
        return OrderedDict(
            fecha=p['fecha'], hora=hora, iso=p['iso'], partido=p['partido'], competencia=p['competencia'],
            nivel=p['tipo_nombre'], marcas=marcas,
            respaldo=f"{p['n_selecciones']} selecciones",
            cuota=cuota, cuota_registrada=p['cuota_registrada'],
            sin_apuesta=False,
            ya_empezo=(p['fecha'] + ' ' + hora) <= ahora if hora else p['fecha'] <= hoy,
            resultado=p['resultado'], detalle='', argumento=p['argumento'],
            selecciones=p['selecciones'], parley=p['parley'], tipo=p['tipo'],
        )

    bots = []
    specs = [
        (over, cardOver, 'Más de 9,5 córners totales', lambda p: True, 'picksters-over-corners.html'),
        (parley, cardParley, 'Parley diario de fútbol (principal y conservador)', lambda p: True, 'parley-picks.html'),
    ]
    for b, fn, mercado, ok, link in specs:
        if b.get('pendiente'):
            bots.append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': mercado, 'link': link,
                         'pendientes': [], 'ayer': [], 'hoy_cerradas': [], 'sin_datos': True})
            continue
        ps = [fn(p) for p in b['picks'] if ok(p)]
        bots.append({'bot': b['bot'], 'nombre': b['nombre'], 'mercado': mercado, 'link': link,
                     'pendientes': sorted([p for p in ps if p['resultado'] == 'pendiente'], key=_sort_key),
                     'ayer': sorted([p for p in ps if p['fecha'] == ayer and p['resultado'] in cerrados], key=_sort_key),
                     'hoy_cerradas': sorted([p for p in ps if p['fecha'] == hoy and p['resultado'] in cerrados], key=_sort_key),
                     'balance': b['resumen']})
    return {'generado': ahora, 'generado_iso': now_iso(), 'zona_origen': 'America/Bogota (UTC-5)',
            'hoy': hoy, 'ayer': ayer, 'bots': bots}


def main():
    os.makedirs(OUT, exist_ok=True)
    sync_fuentes()
    bots = [build_over(), build_parley()]
    for stale in ('corners_10min.json', 'corners_vivo.json'):
        sp = os.path.join(OUT, stale)
        if os.path.exists(sp):
            os.remove(sp)
            print('Eliminado', stale)
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
    pdd = build_picks_del_dia(bots[0], bots[1])
    with open(os.path.join(OUT, 'picks_del_dia.json'), 'w', encoding='utf-8') as f:
        json.dump(pdd, f, ensure_ascii=False, indent=1)
    revisa_publicado()
    for b in bots:
        s = b.get('resumen')
        if s:
            print(f"{b['nombre']}: {s['aciertos']}/{s['resueltas']} ({s['pct']} %), {s['unidades']:+.2f} u, "
                  f"pendientes {s['pendientes']}, otros {s['otros']}"
                  + (f", sin cuota combinada {s['sin_cuota']}" if s.get('sin_cuota') else ''))
        for a in b.get('avisos', []):
            print('  aviso:', a)
        if b['bot'] == 'parley_picks' and not b.get('pendiente'):
            for n in b['por_tipo']:
                print(f"  {n['grupo']}: {n['aciertos']}/{n['resueltas']} ({n['pct']} %), {n['unidades']:+.2f} u"
                      + (f" (sin cuota {n['sin_cuota']})" if n.get('sin_cuota') else ''))
            rs = b['resumen_selecciones']
            print(f"  selecciones sueltas (sin unidades): {rs['aciertos']}/{rs['resueltas']} ({rs['pct']} %)")
    print(f"\nPicks del día (generado {pdd['generado_iso']}):")
    for b in pdd['bots']:
        print(f"- {b['nombre']}: {len(b['pendientes'])} pendientes")
        for p in b['pendientes']:
            print(f"    {p['fecha']} {p['hora']}  {p['partido']} ({p['competencia']}) · {p['respaldo']} · cuota {p['cuota']} · {', '.join(p['marcas']) or '—'}")
            print(f"        por qué ({p['argumento']['origen']}): {p['argumento']['texto'][:160]}")
        print(f"  resultados de ayer ({pdd['ayer']}): " + (', '.join(f"{p['partido']} {p['resultado'].upper()}" for p in b['ayer']) or 'ninguno'))


if __name__ == '__main__':
    main()
