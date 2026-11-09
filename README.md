# CórnersPicks — sitio de los bots

Sitio estático (HTML/CSS/JS, sin backend), listo para GitHub Pages.

El sitio documenta dos bots: **Picksters Over Córners** (más de 9,5 córners totales) y **Parley Picks** (parley diario de fútbol).

## Actualizar datos (un solo paso)
`./update.sh` copia el registro vivo de Parley Picks si es más reciente, regenera `data/*.json` (incluido `data/picks_del_dia.json` para la página *Picks del día*) y, si hay cambios, hace commit y push.

### A mano
1. Copia los registros a `../site-data/` (`over_corners.csv`, `parley_picks.csv`).
2. Corre `python3 build_data.py` → regenera `data/*.json`.
3. Sube los cambios. Las gráficas (Chart.js por CDN) se dibujan en el navegador.

## Ver en local
`python3 -m http.server 8000` dentro de esta carpeta y abre http://localhost:8000

## Cuotas
Como la cuota fluctúa en cada casa de apuestas, usamos una cuota promedio de 1,60 para calcular las unidades de Picksters Over Córners. En Parley Picks las unidades salen de la cuota combinada registrada de cada parley (`cuota_total_parley`); si esa columna está vacía, el resultado cuenta en el porcentaje de acierto y las unidades de ese parley quedan sin calcular. Los nombres de casas que no deben aparecer en el sitio van en `../site-data/casas_ocultas.txt` (fuera del repo); `build_data.py` los cambia por un genérico en los textos de los bots y falla si alguno queda en cualquier archivo publicado.

## Horas
`build_data.py` emite cada hora de partido y la de actualización como ISO con offset `-05:00` (`iso`, `generado_iso`). `js/app.js` las convierte con `Intl.DateTimeFormat` a la zona horaria del navegador. Sin JS se ve la hora original con "(UTC-5)".

## Parley Picks
Registro vivo: `/workspace/parley_picks/registro_parleys.csv` (solo lectura) → `../site-data/parley_picks.csv` → `data/parley_picks.json`. Cada pick del sitio es un parley completo (se agrupa por fecha y código P1/P2/P3). El principal y el conservador se cuentan por separado.
