"""La frontera con Kodi.

`core/` no importa `xbmc` en ningun punto. Es lo que permite construir y evaluar el
motor sin Kodi delante, y lo que hace que estas 59 pruebas puedan existir. La regla
viene de `kodi-addon-cec`, donde tambien hay un test que la vigila: sin el, la
frontera se cruza sola en el primer apuro.
"""

import ast
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUCLEO = os.path.join(RAIZ, "core")
PROHIBIDOS = ("xbmc", "xbmcgui", "xbmcvfs", "xbmcaddon", "xbmcplugin")


def _fuentes(directorio):
    for base, _, ficheros in os.walk(directorio):
        for fichero in ficheros:
            if fichero.endswith(".py"):
                yield os.path.join(base, fichero)


def _importados(ruta):
    with open(ruta, encoding="utf-8") as handle:
        arbol = ast.parse(handle.read(), filename=ruta)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield alias.name.split(".")[0]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            yield nodo.module.split(".")[0]


def test_el_nucleo_no_importa_kodi():
    for ruta in _fuentes(NUCLEO):
        culpables = [m for m in _importados(ruta) if m in PROHIBIDOS]
        assert not culpables, "%s importa %s" % (os.path.relpath(ruta, RAIZ), culpables)


def test_el_nucleo_no_usa_dependencias_externas():
    """En el repositorio oficial de Kodi no hay `numpy`, `scipy`, `pandas` ni
    `scikit-learn`: comprobado sobre los 1.075 complementos de Omega. Lo que no
    este en la libreria estandar no se puede instalar donde esto va a correr."""
    permitidos = {"math", "json", "os", "sys", "re", "time", "collections", "itertools",
                  "functools", "datetime", "unicodedata", "adviser"}
    for ruta in _fuentes(NUCLEO):
        for modulo in _importados(ruta):
            assert modulo in permitidos, "%s importa %s" % (os.path.relpath(ruta, RAIZ), modulo)
