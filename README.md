# CórnersPicks — sitio de los bots

Sitio estático (HTML/CSS/JS, sin backend), listo para GitHub Pages.

## Actualizar datos (un solo paso)
`./update.sh` copia el registro vivo del Bot Corners 10 Minutos, regenera `data/*.json` (incluido `data/picks_del_dia.json` para la página *Picks del día*) y, si hay cambios, hace commit y push.

### A mano
1. Copia los registros a `../site-data/` (`corners_10min.csv`, `over_corners.csv`).
2. Corre `python3 build_data.py` → regenera `data/*.json`.
3. Sube los cambios. Las gráficas (Chart.js por CDN) se dibujan en el navegador.

## Ver en local
`python3 -m http.server 8000` dentro de esta carpeta y abre http://localhost:8000

## Cuotas
Como la cuota fluctúa en cada casa de apuestas, usamos una cuota promedio de 1,60 para calcular las unidades. Los nombres de casas que no deben aparecer en el sitio van en `../site-data/casas_ocultas.txt` (fuera del repo); `build_data.py` los cambia por un genérico en los textos de los bots y falla si alguno queda en cualquier archivo publicado.

## Horas
`build_data.py` emite cada hora de partido y la de actualización como ISO con offset `-05:00` (`iso`, `generado_iso`). `js/app.js` las convierte con `Intl.DateTimeFormat` a la zona horaria del navegador. Sin JS se ve la hora original con "(UTC-5)".

## Cornes en Vivo
Registro vivo: `/workspace/corners/registro.csv` (solo lectura) → `../site-data/corners_vivo.csv` → `data/corners_vivo.json`. Picks = filas con señal MÁS o MENOS; cuota supuesta 1,90 (acierto +0,90, error −1, nulo 0).
