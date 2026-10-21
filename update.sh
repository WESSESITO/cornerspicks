#!/usr/bin/env bash
# Actualización de un solo paso del sitio CórnersPicks.
# 1) Copia el registro vivo del Bot Corners 10 Minutos (si es más reciente)
# 2) Regenera data/*.json (incluye data/picks_del_dia.json)
# 3) Si hay cambios: git add -A, commit "Actualización <fecha hora Bogotá>" y push (sin force)
set -euo pipefail
cd "$(dirname "$0")"
export TZ=America/Bogota
LIVE=/workspace/corners/picks_log.csv
DST=../site-data/corners_10min.csv
if [[ -f "$LIVE" && ( ! -f "$DST" || "$LIVE" -nt "$DST" ) ]]; then
  cp -p "$LIVE" "$DST" && echo "Copiado $LIVE -> $DST"
fi
git config --get credential.https://github.com.helper >/dev/null 2>&1 || gh auth setup-git
VIVO=/workspace/corners/registro.csv          # Cornes en Vivo (no confundir con picks_log.csv ni registro_corners.csv)
VDST=../site-data/corners_vivo.csv
if [[ -f "$VIVO" && ( ! -f "$VDST" || "$VIVO" -nt "$VDST" ) ]]; then
  cp -p "$VIVO" "$VDST" && echo "Copiado $VIVO -> $VDST"
fi
ARGS=/workspace/corners/picks_argumentos.csv
ADST=../site-data/corners_10min_argumentos.csv
if [[ -f "$ARGS" && ( ! -f "$ADST" || "$ARGS" -nt "$ADST" ) ]]; then
  cp -p "$ARGS" "$ADST" && echo "Copiado $ARGS -> $ADST"
fi
[[ -f ../site-data/over_corners.csv ]] || echo "AVISO: falta ../site-data/over_corners.csv (Picksters Over Córners)"
python3 build_data.py
if [[ -n "$(git status --porcelain)" ]]; then
  STAMP="$(date '+%Y-%m-%d %H:%M') (hora Bogotá)"
  git add -A
  git commit -q -m "Actualización $STAMP"
  echo "Commit: Actualización $STAMP"
else
  echo "Sin cambios nuevos en los datos."
fi
git fetch -q origin main
if [[ -n "$(git log --oneline origin/main..HEAD)" ]]; then
  git pull -q --rebase origin main || { echo "ERROR: no se pudo integrar origin/main; revisa a mano"; exit 1; }
  git push -q origin HEAD:main
  echo "Publicado ($(git rev-parse --short HEAD)): https://wessesito.github.io/cornerspicks/picks-del-dia.html (GitHub Pages tarda ~1 min)"
else
  echo "Nada pendiente de publicar."
fi
