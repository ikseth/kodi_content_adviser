"""El indice se escribe entero o no se escribe.

Un indice a medio escribir es peor que no tener indice: el addon arrancaria y
fallaria al leerlo.
"""

import os

from adviser.storage import load, save


def test_viaje_de_ida_y_vuelta(tmp_path):
    destino = str(tmp_path / "sub" / "indice.json")
    datos = {"version": 1, "vectors": {"1": {"genre:accion": 1.5}}, "titulo": "Ñandú"}
    save(destino, datos)
    assert load(destino) == datos


def test_no_deja_temporales_detras(tmp_path):
    destino = str(tmp_path / "indice.json")
    save(destino, {"a": 1})
    save(destino, {"a": 2})
    assert os.listdir(str(tmp_path)) == ["indice.json"]


def test_reescribir_sustituye_el_contenido(tmp_path):
    destino = str(tmp_path / "indice.json")
    save(destino, {"a": 1})
    save(destino, {"b": 2})
    assert load(destino) == {"b": 2}
