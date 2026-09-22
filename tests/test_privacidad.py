"""Este repositorio es publico: no puede llevar datos de una instalacion concreta.

No es una precaucion teorica: la documentacion de trabajo llego a nombrar equipos,
direcciones internas y una zona DNS privada, y estuvo a punto de publicarse.

**Los nombres de maquina no se pueden comprobar con una regla** —cualquier palabra
puede serlo—, asi que esta prueba cubre lo que si tiene forma reconocible: las
direcciones privadas y las zonas DNS internas. Lo demas es criterio al escribir.
"""

import os
import re
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rangos privados de la RFC 1918, mas los enlaces locales.
PRIVADAS = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}(?:\.\d{1,3})?"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3})\b")

# Dominios de uso interno habitual. `.local` no entra: lo usa mDNS y sale en
# documentacion legitima.
ZONAS = re.compile(r"\b[a-z0-9-]+\.(?:lan|internal|intranet|home\.arpa)\b", re.I)

# Salvoconductos, y cada uno por un motivo: son direcciones que no dicen nada de
# la red de nadie.
PERMITIDOS = ("127.0.0.1", "0.0.0.0", "localhost")


def _versionados():
    salida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                            text=True, timeout=60)
    assert salida.returncode == 0, salida.stderr
    return [f for f in salida.stdout.splitlines() if f]


def _lineas_sospechosas():
    hallazgos = []
    for relativo in _versionados():
        ruta = os.path.join(RAIZ, relativo)
        try:
            with open(ruta, encoding="utf-8") as handle:
                contenido = handle.read()
        except (OSError, UnicodeDecodeError):
            continue  # binario o ilegible: no es texto que revele nada
        for numero, linea in enumerate(contenido.splitlines(), 1):
            if any(p in linea for p in PERMITIDOS):
                continue
            if PRIVADAS.search(linea) or ZONAS.search(linea):
                hallazgos.append("%s:%d: %s" % (relativo, numero, linea.strip()[:90]))
    return hallazgos


def test_hay_ficheros_versionados():
    """Si esto falla, el resto de la prueba no esta mirando nada."""
    assert len(_versionados()) > 10


def test_no_se_versionan_direcciones_ni_zonas_internas():
    hallazgos = _lineas_sospechosas()
    assert not hallazgos, "datos de una red concreta en el repositorio:\n  " + \
        "\n  ".join(hallazgos)


def test_no_se_versiona_la_documentacion_de_trabajo():
    """`docs/` describe una instalacion concreta, no el complemento.

    Lleva cifras de un catalogo concreto, titulos reales, los equipos donde se
    midio y donde se publican los ZIP. Nada de eso es del complemento: vive fuera
    del repositorio, y esta prueba evita que vuelva a entrar por un `git add`
    distraido.
    """
    intrusos = [f for f in _versionados() if f.startswith("docs/")]
    assert not intrusos, (
        "documentacion de trabajo versionada:\n  " + "\n  ".join(intrusos))
