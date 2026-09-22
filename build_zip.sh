#!/usr/bin/env bash
# Empaqueta el add-on en un ZIP instalable para Kodi.
# Uso: ./build_zip.sh [DIRECTORIO_ADDON]
#
# El build inyecta `core/adviser` dentro de `lib/` del addon antes de empaquetar,
# porque Kodi instala cada addon como paquete autocontenido y no puede depender en
# runtime de carpetas hermanas del repositorio.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Por defecto se empaqueta SIN la capa de IA. La garantia de que una instalacion
# no la lleva es que el codigo no viaja, no un ajuste que alguien pueda cambiar;
# es la misma regla que el suscriptor de `kodi-addon-nextcloud`.
WITH_AI=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --with-ai) WITH_AI=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done

ADDON_DIR_REL="${ARGS[0]:-addon/plugin.video.content.adviser}"
ADDON_DIR="${ROOT_DIR}/${ADDON_DIR_REL}"
[ -d "$ADDON_DIR" ] || { echo "ERROR: No existe $ADDON_DIR"; exit 1; }
[ -f "$ADDON_DIR/addon.xml" ] || { echo "ERROR: Falta $ADDON_DIR/addon.xml"; exit 1; }

ADDON_NAME="$(basename "$ADDON_DIR")"
ADDON_ID=$(sed -n 's/.*<addon[^>]* id="\([^"]*\)".*/\1/p' "$ADDON_DIR/addon.xml" | head -n 1)
VERSION=$(sed -n 's/.*<addon[^>]* version="\([^"]*\)".*/\1/p' "$ADDON_DIR/addon.xml" | head -n 1)
[ -n "$ADDON_ID" ] || { echo "ERROR: No se pudo leer el id del add-on"; exit 1; }
[ -n "$VERSION" ] || { echo "ERROR: No se pudo leer la version del add-on"; exit 1; }

DIST_DIR="${ROOT_DIR}/dist"
mkdir -p "$DIST_DIR"

STAGING_ROOT=$(mktemp -d)
cleanup() { rm -rf "$STAGING_ROOT"; }
trap cleanup EXIT

STAGED="${STAGING_ROOT}/${ADDON_NAME}"
mkdir -p "${STAGED}/lib"
cp -R "${ADDON_DIR}/." "${STAGED}/"
cp -R "${ROOT_DIR}/core/adviser" "${STAGED}/lib/"

# El nombre limpio es el de la variante que se publica. La que lleva la capa de
# IA es la excepcion y lo dice en el nombre: un ZIP que no anuncia lo que trae
# acaba instalado donde no se queria.
if [ "$WITH_AI" -eq 0 ]; then
  python3 "${ROOT_DIR}/tools/strip_ai.py" "$STAGED"
  SUFFIX=""
else
  SUFFIX="+ai"
fi

# xbmcvfs genera .pyc en runtime; no viajan en el paquete.
find "$STAGED" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGED" -name '*.py[co]' -delete 2>/dev/null || true

# La version la decide el manifiesto; el sufijo, si lleva la capa de IA. Kodi
# admite `+` en la version y asi el nombre del ZIP no miente sobre su contenido.
OUT_ZIP="${DIST_DIR}/${ADDON_ID}-${VERSION}${SUFFIX}.zip"
echo "==> Empaquetando ${ADDON_ID} v${VERSION}${SUFFIX} -> ${OUT_ZIP}"

rm -f "$OUT_ZIP"
if command -v zip >/dev/null 2>&1; then
  ( cd "$STAGING_ROOT" && zip -r -9 -q "$OUT_ZIP" "$ADDON_NAME" )
else
  python3 - "$STAGING_ROOT" "$ADDON_NAME" "$OUT_ZIP" <<'PYZIP'
import os, sys, zipfile
parent, name, out_zip = sys.argv[1:4]
with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, dirs, files in os.walk(os.path.join(parent, name)):
        dirs.sort()
        for filename in sorted(files):
            full = os.path.join(root, filename)
            zf.write(full, os.path.relpath(full, parent))
PYZIP
fi

( cd "$DIST_DIR" && sha256sum "$(basename "$OUT_ZIP")" > "$(basename "$OUT_ZIP").sha256" )
echo "OK: ${OUT_ZIP}"
