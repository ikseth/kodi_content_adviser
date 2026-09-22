"""El contrato del addon: nada de ajustes decorativos ni textos que falten.

Dos reglas heredadas de los proyectos hermanos, y las dos por algo que paso:

- `kodi-addon-nextcloud` arrastra ajustes en la interfaz **sin implementacion
  detras** desde el principio. Aqui un ajuste que no lea nadie rompe la prueba.
- En `kodi-addon-cec`, toda accion publica necesita su entrada en los **dos**
  `strings.po`, y hay un test que lo vigila. Un texto que falte sale en pantalla
  como un numero.
"""

import ast
import os
import re
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(RAIZ, "addon", "plugin.video.content.adviser")
IDIOMAS = ("resource.language.es_es", "resource.language.en_gb")


def _codigo():
    partes = []
    for base, _, ficheros in os.walk(ADDON):
        if "lib" + os.sep + "adviser" in base:
            continue
        for fichero in ficheros:
            if fichero.endswith(".py"):
                with open(os.path.join(base, fichero), encoding="utf-8") as handle:
                    partes.append(handle.read())
    return "\n".join(partes)


def _ajustes():
    arbol = ET.parse(os.path.join(ADDON, "resources", "settings.xml"))
    return [s.get("id") for s in arbol.getroot().iter("setting") if s.get("id")]


def _cadenas(idioma):
    ruta = os.path.join(ADDON, "resources", "language", idioma, "strings.po")
    with open(ruta, encoding="utf-8") as handle:
        return set(re.findall(r'msgctxt "#(\d+)"', handle.read()))


def _ids_referenciados():
    ids = set(re.findall(r"localise\((\d+)\)", _codigo()))
    for fichero in ("resources/settings.xml", "addon.xml"):
        with open(os.path.join(ADDON, fichero), encoding="utf-8") as handle:
            contenido = handle.read()
        ids.update(re.findall(r'(?:label|help)="(\d+)"', contenido))
        ids.update(re.findall(r"<label>(\d+)</label>", contenido))
    return ids


def test_hay_ajustes():
    assert _ajustes(), "si esto falla, el resto de pruebas no comprueba nada"


def test_todo_ajuste_lo_lee_alguien():
    codigo = _codigo()
    huerfanos = [i for i in _ajustes() if '"%s"' % i not in codigo]
    assert not huerfanos, "ajustes sin implementacion detras: %s" % huerfanos


def test_todo_texto_referenciado_existe_en_los_dos_idiomas():
    referenciados = _ids_referenciados()
    assert referenciados
    for idioma in IDIOMAS:
        faltan = sorted(referenciados - _cadenas(idioma))
        assert not faltan, "faltan en %s: %s" % (idioma, faltan)


def test_los_dos_idiomas_llevan_los_mismos_identificadores():
    uno, otro = (_cadenas(i) for i in IDIOMAS)
    assert uno == otro, "descuadre: %s" % sorted(uno ^ otro)


def test_el_manifiesto_declara_lo_que_el_addon_hace():
    arbol = ET.parse(os.path.join(ADDON, "addon.xml")).getroot()
    puntos = {e.get("point") for e in arbol.findall("extension")}
    assert "xbmc.python.pluginsource" in puntos, "sin listado no hay recomendaciones"
    assert "xbmc.service" in puntos, "sin servicio nadie construye el indice"
    assert "kodi.context.item" in puntos, "sin menu contextual no hay «similares a esta»"


def test_el_menu_contextual_solo_aparece_donde_tiene_sentido():
    """Una entrada visible sobre cualquier cosa es ruido en el menu de todo el mundo."""
    arbol = ET.parse(os.path.join(ADDON, "addon.xml")).getroot()
    visible = arbol.find(".//item/visible").text
    assert "ListItem.DBType" in visible


def test_si_se_reutiliza_el_interprete_no_puede_haber_estado_de_modulo():
    """`reuselanguageinvoker` no vuelve a importar el modulo entre invocaciones.

    Cualquier variable de nivel de modulo que salga de `sys.argv` se quedaria
    congelada en la primera llamada: el listado se pintaria en el `handle` de la
    invocacion anterior. Es el fallo clasico de esa opcion, y no da error: da
    resultados en el sitio equivocado.
    """
    arbol = ET.parse(os.path.join(ADDON, "addon.xml")).getroot()
    reutiliza = arbol.find(".//reuselanguageinvoker")
    if reutiliza is None or reutiliza.text != "true":
        return
    for base, _, ficheros in os.walk(ADDON):
        if "lib" + os.sep + "adviser" in base:
            continue
        for fichero in ficheros:
            if not fichero.endswith(".py"):
                continue
            ruta = os.path.join(base, fichero)
            with open(ruta, encoding="utf-8") as handle:
                arbol_py = ast.parse(handle.read(), filename=ruta)
            for nodo in arbol_py.body:
                if not isinstance(nodo, ast.Assign):
                    continue
                usa_argv = any(
                    isinstance(n, ast.Attribute) and n.attr == "argv"
                    for n in ast.walk(nodo))
                assert not usa_argv, (
                    "%s guarda sys.argv en una variable de modulo"
                    % os.path.relpath(ruta, RAIZ))
