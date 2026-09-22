#!/usr/bin/env bash
# Genera el clon de Estuary con la fila del recomendador.
#
# Uso: ./build_skin.sh RUTA_A_SKIN_ESTUARY
#
# Hay que darle el Estuary de la version de Kodi que se vaya a usar: el clon se
# regenera en cada version, no se arrastra. Donde encontrarlo:
#
#   Flatpak    flatpak run --command=sh --filesystem=/tmp tv.kodi.Kodi \
#                  -c 'cp -r /app/share/kodi/addons/skin.estuary /tmp/estuary'
#   LibreELEC  /usr/share/kodi/addons/skin.estuary
#   Debian     /usr/share/kodi/addons/skin.estuary

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${1:-}"
[ -n "$SOURCE" ] || { echo "ERROR: falta la ruta al skin.estuary de origen"; exit 1; }
[ -f "$SOURCE/addon.xml" ] || { echo "ERROR: $SOURCE no contiene addon.xml"; exit 1; }

STAGING=$(mktemp -d)
cleanup() { rm -rf "$STAGING"; }
trap cleanup EXIT

SKIN_ID="skin.estuary.adviser"
DEST="${STAGING}/${SKIN_ID}"
cp -r "$SOURCE" "$DEST"
chmod -R u+w "$DEST"

VERSION=$(python3 - "$DEST" <<'PYPATCH'
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(".")), "skin"))
sys.path.insert(0, "skin")
import patch
info = patch.apply(sys.argv[1])
sys.stderr.write("clon de Estuary %s -> %s %s\n"
                 % (info["upstream_version"], info["skin_id"], info["version"]))
print(info["version"])
PYPATCH
)

DIST_DIR="${ROOT_DIR}/dist"
mkdir -p "$DIST_DIR"
OUT_ZIP="${DIST_DIR}/${SKIN_ID}-${VERSION}.zip"
rm -f "$OUT_ZIP"

if command -v zip >/dev/null 2>&1; then
  ( cd "$STAGING" && zip -r -9 -q "$OUT_ZIP" "$SKIN_ID" )
else
  python3 - "$STAGING" "$SKIN_ID" "$OUT_ZIP" <<'PYZIP'
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
