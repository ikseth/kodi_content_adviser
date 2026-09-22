"""El ZIP tiene que ser instalable y autocontenido.

Kodi instala cada addon como paquete autocontenido: **no puede depender en runtime
de carpetas hermanas del repositorio**. Si el nucleo no viaja dentro, el addon
falla en el equipo del usuario y no aqui.
"""

import os
import re
import subprocess
import zipfile

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(RAIZ, "addon", "plugin.video.content.adviser")


@pytest.fixture(scope="module")
def paquete():
    proceso = subprocess.run([os.path.join(RAIZ, "build_zip.sh")],
                             cwd=RAIZ, capture_output=True, text=True, timeout=300)
    assert proceso.returncode == 0, proceso.stderr
    with open(os.path.join(ADDON, "addon.xml"), encoding="utf-8") as handle:
        # Ojo: `version="1.0"` tambien esta en la declaracion XML de la primera
        # linea. Hay que anclar en el elemento <addon>, como hace build_zip.sh.
        version = re.search(r'<addon[^>]* version="([^"]+)"', handle.read()).group(1)
    ruta = os.path.join(RAIZ, "dist", "plugin.video.content.adviser-%s.zip" % version)
    assert os.path.exists(ruta)
    with zipfile.ZipFile(ruta) as zf:
        yield zf.namelist()


def test_el_nucleo_viaja_dentro(paquete):
    assert any(n.endswith("lib/adviser/domain/index.py") for n in paquete)
    assert any(n.endswith("lib/adviser/library/reader.py") for n in paquete)


def test_van_los_puntos_de_entrada_y_la_configuracion(paquete):
    for esperado in ("addon.xml", "default.py", "service.py", "context.py",
                     "resources/settings.xml"):
        assert any(n.endswith(esperado) for n in paquete), "falta %s" % esperado


def test_van_los_dos_idiomas(paquete):
    for idioma in ("es_es", "en_gb"):
        assert any("resource.language.%s/strings.po" % idioma in n for n in paquete)


def test_no_viajan_residuos_de_compilacion(paquete):
    """xbmcvfs genera .pyc en runtime; no tienen por que ir en el paquete."""
    basura = [n for n in paquete if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]
    assert not basura, basura


def test_todo_cuelga_de_una_sola_carpeta_con_el_id_del_addon(paquete):
    """Kodi lo exige: si no, la instalacion desde ZIP falla."""
    raices = {n.split("/")[0] for n in paquete}
    assert raices == {"plugin.video.content.adviser"}


# --- las dos variantes -------------------------------------------------------
import sys  # noqa: E402

sys.path.insert(0, os.path.join(RAIZ, "tools"))
from strip_ai import STRING_IDS  # noqa: E402


def _construir(argumentos, sufijo):
    proceso = subprocess.run([os.path.join(RAIZ, "build_zip.sh")] + argumentos,
                             cwd=RAIZ, capture_output=True, text=True, timeout=300)
    assert proceso.returncode == 0, proceso.stderr
    with open(os.path.join(ADDON, "addon.xml"), encoding="utf-8") as handle:
        version = re.search(r'<addon[^>]* version="([^"]+)"', handle.read()).group(1)
    ruta = os.path.join(RAIZ, "dist",
                        "plugin.video.content.adviser-%s%s.zip" % (version, sufijo))
    assert os.path.exists(ruta), ruta
    return zipfile.ZipFile(ruta)


@pytest.fixture(scope="module")
def sin_ia():
    with _construir([], "") as zf:
        yield zf


@pytest.fixture(scope="module")
def con_ia():
    with _construir(["--with-ai"], "+ai") as zf:
        yield zf


def test_la_variante_publicada_no_lleva_el_codigo_de_ia(sin_ia):
    """La garantia es estructural, no un ajuste: si el codigo no viaja, no hay
    nada que activar por error. Misma regla que el suscriptor del hermano."""
    sospechosos = [n for n in sin_ia.namelist()
                   if n.endswith("/ai.py") or "/adviser/ai/" in n]
    assert not sospechosos, sospechosos


def test_la_variante_publicada_no_deja_ajustes_huerfanos(sin_ia):
    """Un ajuste en la interfaz sin implementacion detras es el problema que el
    proyecto hermano arrastra desde el principio."""
    ajustes = sin_ia.read(
        "plugin.video.content.adviser/resources/settings.xml").decode("utf-8")
    assert 'id="ai"' not in ajustes
    assert "ai_enabled" not in ajustes


def test_la_variante_publicada_no_deja_textos_sueltos(sin_ia):
    for nombre in sin_ia.namelist():
        if not nombre.endswith("strings.po"):
            continue
        contenido = sin_ia.read(nombre).decode("utf-8")
        for string_id in STRING_IDS:
            assert 'msgctxt "#%d"' % string_id not in contenido, (nombre, string_id)


def test_la_variante_con_ia_si_lo_lleva_todo(con_ia):
    """Si esto pasara sin llevarlo, la prueba de arriba no estaria comprobando nada."""
    assert any("/adviser/ai/" in n for n in con_ia.namelist())
    ajustes = con_ia.read(
        "plugin.video.content.adviser/resources/settings.xml").decode("utf-8")
    assert 'id="ai"' in ajustes


def test_las_dos_variantes_comparten_el_resto(sin_ia, con_ia):
    """La diferencia tiene que ser exactamente la capa de IA y nada mas."""
    solo_en_ia = set(con_ia.namelist()) - set(sin_ia.namelist())
    assert all(n.endswith("/ai.py") or "/adviser/ai/" in n for n in solo_en_ia)
    assert not set(sin_ia.namelist()) - set(con_ia.namelist())


def test_la_variante_publicada_no_tiene_importaciones_colgando(sin_ia):
    """Retirar de mas deja un paquete que revienta al arrancar, no al usarse.

    Paso: al quitar `phrases.py` de la variante sin IA, `catalogue.py` seguia
    importandolo al cargar. El ZIP se construia igual y el fallo solo aparecia en
    el equipo del usuario. Esta prueba resuelve cada importacion del nucleo
    contra lo que de verdad viaja dentro.
    """
    import ast

    presentes = set(sin_ia.namelist())
    raiz = "plugin.video.content.adviser/"

    def existe(modulo):
        ruta = raiz + "lib/" + modulo.replace(".", "/")
        return (ruta + ".py") in presentes or (ruta + "/__init__.py") in presentes

    def _expone(zf, modulo, nombres):
        ruta = raiz + "lib/" + modulo.replace(".", "/")
        fichero = ruta + ".py" if (ruta + ".py") in presentes else ruta + "/__init__.py"
        arbol = ast.parse(zf.read(fichero).decode("utf-8"), filename=fichero)
        definidos = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.ClassDef)):
                definidos.add(nodo.name)
            elif isinstance(nodo, ast.Assign):
                definidos.update(t.id for t in nodo.targets if isinstance(t, ast.Name))
            elif isinstance(nodo, ast.Import):
                definidos.update((a.asname or a.name).split(".")[0] for a in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                definidos.update(a.asname or a.name for a in nodo.names)
        return all(n in definidos for n in nombres)

    for nombre in presentes:
        if not nombre.endswith(".py"):
            continue
        arbol = ast.parse(sin_ia.read(nombre).decode("utf-8"), filename=nombre)
        # **Solo los de nivel de modulo**: son los que se ejecutan al cargar. Una
        # importacion dentro de una funcion, o envuelta en un `try`, es
        # justamente como se declara una capa opcional, y romperla ahi es
        # deliberado.
        for nodo in arbol.body:
            modulos = []
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
                modulos = [nodo.module]
            for modulo in modulos:
                if modulo.split(".")[0] != "adviser":
                    continue
                assert existe(modulo), "%s importa %s al cargar, y no viaja en el ZIP" % (
                    nombre, modulo)

            # **Y que los nombres existan de verdad.** Que el modulo viaje no
            # basta: `BASIC_TVSHOW_FIELDS` estaba definido pero sin reexportar en
            # su `__init__`, y el complemento no arrancaba. La prueba anterior lo
            # daba por bueno porque el modulo si estaba.
            if isinstance(nodo, ast.ImportFrom) and nodo.module \
                    and nodo.module.split(".")[0] == "adviser" and nodo.level == 0:
                assert _expone(sin_ia, nodo.module, [a.name for a in nodo.names]), (
                    "%s importa de %s nombres que ese modulo no expone"
                    % (nombre, nodo.module))


def test_el_indice_declara_un_formato_que_sube_al_ganar_artefactos():
    """Sin esto, un equipo que actualiza se queda con los ficheros de la version
    anterior: existen los que se miraban, asi que no reconstruye, y el artefacto
    nuevo no aparece nunca. Paso de verdad al subir un nodo de 0.3.0 a 0.4.1.
    """
    ruta = os.path.join(ADDON, "resources", "lib", "catalogue.py")
    with open(ruta, encoding="utf-8") as handle:
        fuente = handle.read()
    assert "FORMAT_VERSION" in fuente
    # Lo que `build` deja escrito esta declarado, y todo se comprueba antes de
    # decidir que no hace falta reconstruir.
    assert "BUILD_ARTIFACTS" in fuente
    cuerpo = fuente[fuente.index("def needs_rebuild"):]
    assert "BUILD_ARTIFACTS" in cuerpo, "needs_rebuild no recorre los artefactos"
    declarados = fuente[fuente.index("BUILD_ARTIFACTS = ("):]
    declarados = declarados[:declarados.index(")")]
    for esperado in ("INDEX_FILE", "PREFIX_DIR", "PHRASES_FILE", "STATE_FILE"):
        assert esperado in declarados, "%s no esta entre los artefactos" % esperado
    assert "HISTORY_FILE" not in declarados, (
        "el historial es del usuario: exigirlo obligaria a reconstruir sin motivo")
