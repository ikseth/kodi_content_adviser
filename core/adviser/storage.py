"""Persistencia del indice.

JSON y nada mas: es lo unico que se puede dar por disponible en cualquier equipo
donde corra Kodi. Se escribe de forma atomica —fichero temporal y `os.replace`—
porque un indice a medio escribir es peor que no tener indice: el addon arrancaria
y fallaria al leerlo.
"""

import json
import os

__all__ = ["save", "load"]


def save(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, path)
    return path


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
