"""Los puntos de entrada tienen que arrancar como proceso.

En `kodi-addon-nextcloud`, **841 pruebas no vieron un `NameError`** porque ninguna
llegaba a ejecutar el programa. Estas dos si lo ejecutan.
"""

import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERRAMIENTAS = [os.path.join(RAIZ, "tools", n) for n in ("build_index.py", "evaluate.py")]


@pytest.mark.parametrize("herramienta", HERRAMIENTAS, ids=os.path.basename)
def test_la_herramienta_arranca_y_explica_lo_que_hace(herramienta):
    proceso = subprocess.run([sys.executable, herramienta, "--help"],
                             capture_output=True, text=True, timeout=60)
    assert proceso.returncode == 0, proceso.stderr
    assert "usage" in proceso.stdout


@pytest.mark.parametrize("herramienta", HERRAMIENTAS, ids=os.path.basename)
def test_sin_configuracion_falla_con_un_mensaje_y_no_con_una_traza(herramienta):
    """Un fichero de credenciales que no existe es el error mas probable de todos.
    Tiene que decirlo, no vomitar una traza."""
    proceso = subprocess.run(
        [sys.executable, herramienta, "--config", os.path.join(RAIZ, "no-existe.env")],
        capture_output=True, text=True, timeout=60)
    assert proceso.returncode != 0
    assert "Traceback" not in proceso.stderr
    assert proceso.stderr.strip(), "tiene que explicar que ha pasado"
