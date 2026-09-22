"""Quita la capa de IA de un addon ya preparado para empaquetar.

**La garantia es estructural, no un ajuste.** Es la misma regla que
`kodi-addon-nextcloud` aplica a su suscriptor: el ZIP no lleva el codigo de
escritura, y por eso no puede escribir aunque alguien toque un ajuste. Aqui igual:
en la variante sin IA **no viaja ni el codigo, ni los ajustes, ni los textos**, asi
que no hay nada que activar por error ni ajuste huerfano en la interfaz.

Se ejecuta sobre la copia de trabajo del empaquetado, nunca sobre el repositorio.
"""

import argparse
import os
import re
import shutil
import sys

# Lo que define la capa: dos rutas de codigo, una categoria de ajustes y el rango
# de textos que solo usa ella.
# Solo la capa de IA. `phrases.py` **no** se retira aunque solo la use el modo
# de composicion: `catalogue.py` lo importa al cargar, asi que quitarlo dejaria
# un paquete que revienta al arrancar. Cinco kilobytes de codigo de dominio
# inerte cuestan menos que eso.
CODE_PATHS = (os.path.join("resources", "lib", "ai.py"),
              os.path.join("lib", "adviser", "ai"))
SETTINGS_CATEGORY = "ai"
STRING_IDS = (30002, 30036, 30037, 30038, 30039,
              30140, 30141, 30142, 30143, 30144, 30145, 30146, 30147, 30148,
              30191, 30192, 30193, 30194, 30195, 30042, 30149, 30196)

__all__ = ["strip", "CODE_PATHS", "STRING_IDS", "SETTINGS_CATEGORY"]


def _remove_code(addon_dir):
    removed = []
    for relative in CODE_PATHS:
        path = os.path.join(addon_dir, relative)
        if os.path.isdir(path):
            shutil.rmtree(path)
            removed.append(relative)
        elif os.path.isfile(path):
            os.remove(path)
            removed.append(relative)
    return removed


def _remove_settings(addon_dir):
    path = os.path.join(addon_dir, "resources", "settings.xml")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    pattern = re.compile(
        r'[ \t]*<category id="%s".*?</category>\n' % re.escape(SETTINGS_CATEGORY),
        re.DOTALL)
    stripped, count = pattern.subn("", text)
    if not count:
        raise SystemExit("no se encontro la categoria de ajustes de IA en %s" % path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(stripped)
    return count


def _remove_strings(addon_dir):
    base = os.path.join(addon_dir, "resources", "language")
    total = 0
    for folder in sorted(os.listdir(base)):
        path = os.path.join(base, folder, "strings.po")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for string_id in STRING_IDS:
            pattern = re.compile(
                r'\nmsgctxt "#%d"\nmsgid "[^"]*"\nmsgstr "[^"]*"\n' % string_id)
            text, count = pattern.subn("\n", text)
            total += count
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return total


def strip(addon_dir):
    """Devuelve un resumen de lo retirado."""
    return {"code": _remove_code(addon_dir),
            "settings": _remove_settings(addon_dir),
            "strings": _remove_strings(addon_dir)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("addon_dir", help="copia de trabajo del addon")
    args = parser.parse_args(argv)
    summary = strip(args.addon_dir)
    print("retirado: %d ficheros de codigo, %d categoria de ajustes, %d textos"
          % (len(summary["code"]), summary["settings"], summary["strings"]),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
