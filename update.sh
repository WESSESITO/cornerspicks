#!/usr/bin/env bash
# Actualización de un solo paso del sitio CórnersPicks.
# 1) Copia el registro vivo de Parley Picks (si es más reciente)
# 2) Regenera data/*.json (incluye data/picks_del_dia.json)
# 3) Si hay cambios: git add -A, commit "Actualización <fecha hora Bogotá>" y push (sin force)
set -euo pipefail
cd "$(dirname "$0")"
export TZ=America/Bogota
PARLEY=/workspace/parley_picks/registro_parleys.csv
PDST=../site-data/parley_picks.csv
if [[ -f "$PARLEY" && ( ! -f "$PDST" || "$PARLEY" -nt "$PDST" ) ]]; then
  cp -p "$PARLEY" "$PDST" && echo "Copiado $PARLEY -> $PDST"
fi
git config --get credential.https://github.com.helper >/dev/null 2>&1 || gh auth setup-git
[[ -f ../site-data/over_corners.csv ]] || echo "AVISO: falta ../site-data/over_corners.csv (Picksters Over Córners)"
[[ -f ../site-data/parley_picks.csv ]] || echo "AVISO: falta ../site-data/parley_picks.csv (Parley Picks)"
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
