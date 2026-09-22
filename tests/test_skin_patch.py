"""El parche del skin tiene que fallar ruidosamente.

Kodi no tiene herencia de skins, asi que la fila de inicio obliga a clonar
Estuary. Lo que evita que ese clon se pudra es que **se regenera en cada version
de Kodi a partir del Estuary de esa version**, y para eso el parche debe reventar
en cuanto el ancla deje de existir. Un parche que aplica a medias y calla dejaria
un skin sin fila y sin aviso.
"""

import os
import sys
import xml.etree.ElementTree as ET

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "skin"))

import patch  # noqa: E402

MANIFIESTO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<addon id="skin.estuary" version="4.0.0" name="Estuary" provider-name="phil65">\n'
    '  <requires><import addon="xbmc.gui" version="5.17.0"/></requires>\n'
    '</addon>\n'
)


def _estuary_falso(raiz, con_ancla=True, con_teclado=True,
                   con_submenus=True, con_ficha=True, con_actualizar=True):
    os.makedirs(os.path.join(raiz, "xml"), exist_ok=True)
    with open(os.path.join(raiz, "addon.xml"), "w", encoding="utf-8") as handle:
        handle.write(MANIFIESTO)
    cuerpo = patch.ANCHOR + "\t\t\t\t\t\t</include>\n" if con_ancla else "\t\t<!-- otra cosa -->\n"
    with open(os.path.join(raiz, "xml", "Home.xml"), "w", encoding="utf-8") as handle:
        handle.write("<window>\n<controls>\n" + cuerpo + "</controls>\n</window>\n")
    variables = patch.KEYBOARD_ANCHOR + "\t\t<value>algo</value>\n\t</variable>\n" \
        if con_teclado else "\t<variable name=\"Otra\"></variable>\n"
    with open(os.path.join(raiz, "xml", "Variables.xml"), "w", encoding="utf-8") as handle:
        handle.write("<includes>\n" + variables + "</includes>\n")

    submenus = ""
    if con_submenus:
        for anchor_name, _ in patch.SUBMENU:
            submenus += patch._fragment(anchor_name) + "\t\t</content>\n\t</include>\n"
    with open(os.path.join(raiz, "xml", "Includes_Home.xml"), "w", encoding="utf-8") as handle:
        handle.write("<includes>\n" + submenus + "</includes>\n")

    botones = patch.INFO_ANCHOR + '\t\t\t\t\t\t<param name="label" value="x" />\n' \
        "\t\t\t\t\t</include>\n" if con_ficha else "\t\t<!-- otra cosa -->\n"
    with open(os.path.join(raiz, "xml", "DialogVideoInfo.xml"), "w", encoding="utf-8") as handle:
        handle.write("<window>\n<controls>\n" + botones + "</controls>\n</window>\n")

    nav = patch.UPDATE_ANCHOR if con_actualizar else "\t\t<onclick>otra</onclick>\n"
    with open(os.path.join(raiz, "xml", "MyVideoNav.xml"), "w", encoding="utf-8") as handle:
        handle.write("<window>\n<controls>\n<control>\n" + nav
                     + "</control>\n</controls>\n</window>\n")
    return raiz


def test_aplica_y_cambia_la_identidad(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    info = patch.apply(raiz)
    assert info["skin_id"] == patch.SKIN_ID != patch.SOURCE_ID
    with open(os.path.join(raiz, "addon.xml"), encoding="utf-8") as handle:
        manifiesto = handle.read()
    assert 'id="%s"' % patch.SKIN_ID in manifiesto
    assert 'id="%s"' % patch.SOURCE_ID not in manifiesto


def test_la_version_conserva_la_de_origen(tmp_path):
    """Hay que poder saber de que Estuary sale un clon, o no se puede regenerar."""
    info = patch.apply(_estuary_falso(str(tmp_path / "skin")))
    assert info["upstream_version"] == "4.0.0"
    assert info["version"].startswith("4.0.0+")


def test_la_fila_no_se_pone_por_delante_de_continuar_viendo(tmp_path):
    """Continuar una pelicula a medias es mas urgente que una recomendacion, y
    quien la tenia arriba la echo de menos cuando se colo por delante."""
    assert "inprogress_movies.xsp" in patch.ANCHOR


def test_la_fila_queda_en_el_home_y_apunta_al_complemento(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "Home.xml"), encoding="utf-8") as handle:
        home = handle.read()
    assert "plugin://%s/?action=history" % patch.ADVISER_ID in home
    assert "System.AddonIsEnabled(%s)" % patch.ADVISER_ID in home


def test_el_home_sigue_siendo_xml_valido(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    ET.parse(os.path.join(raiz, "xml", "Home.xml"))


def test_revienta_si_estuary_ya_no_tiene_el_ancla(tmp_path):
    """Es el caso que importa: Kodi sube de version y el parche deja de encajar."""
    raiz = _estuary_falso(str(tmp_path / "skin"), con_ancla=False)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)


def test_revienta_si_se_aplica_dos_veces(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)


def test_revienta_si_no_es_un_estuary(tmp_path):
    vacio = str(tmp_path / "vacio")
    os.makedirs(vacio)
    with pytest.raises(patch.PatchError):
        patch.apply(vacio)


def test_la_fila_usa_el_id_real_del_complemento():
    """El skin y el complemento son dos paquetes: si el id se desincroniza, la fila
    queda muda y nada lo avisa."""
    manifiesto = os.path.join(RAIZ, "addon", "plugin.video.content.adviser", "addon.xml")
    real = ET.parse(manifiesto).getroot().get("id")
    assert real == patch.ADVISER_ID


def test_la_cabecera_de_la_fila_existe_en_los_dos_idiomas():
    """La fila toma su titulo del complemento con $ADDON[...]. Si ese texto no
    existe, en pantalla sale un numero."""
    import re
    referencia = re.search(r"\$ADDON\[\S+ (\d+)\]", patch.WIDGET)
    assert referencia, "la cabecera deberia venir del complemento, no ser literal"
    idioma = os.path.join(RAIZ, "addon", "plugin.video.content.adviser",
                          "resources", "language")
    for carpeta in os.listdir(idioma):
        with open(os.path.join(idioma, carpeta, "strings.po"), encoding="utf-8") as handle:
            assert 'msgctxt "#%s"' % referencia.group(1) in handle.read(), carpeta


def test_el_teclado_apunta_al_complemento(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "Variables.xml"), encoding="utf-8") as handle:
        variables = handle.read()
    assert "?action=autocomplete" in variables
    assert patch.ADVISER_ID in variables


def test_el_teclado_conserva_el_comportamiento_original_de_estuary(tmp_path):
    """Se anade un valor delante, no se sustituye: si el complemento se desactiva,
    el teclado vuelve a lo que hacia Estuary en vez de quedarse sin sugerencias."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "Variables.xml"), encoding="utf-8") as handle:
        variables = handle.read()
    nuestro = variables.index(patch.ADVISER_ID)
    original = variables.index("<value>algo</value>")
    assert nuestro < original, "el valor propio tiene que evaluarse primero"


def test_las_variables_siguen_siendo_xml_valido(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    ET.parse(os.path.join(raiz, "xml", "Variables.xml"))


def test_revienta_si_estuary_ya_no_tiene_la_variable_del_teclado(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"), con_teclado=False)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)


def test_preguntar_se_ofrece_en_peliculas_y_en_series(tmp_path):
    """Dos niveles de menu para algo que se quiere a un clic desde el sofa era
    el problema; el widget de categorias es donde el usuario ya mira."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "Includes_Home.xml"), encoding="utf-8") as handle:
        includes = handle.read()
    assert includes.count("?action=ask") == 2
    assert "type=tvshow" in includes


def test_preguntar_solo_se_ofrece_si_hay_a_quien_preguntar(tmp_path):
    """Una entrada que siempre contesta «no esta configurado» es ruido en el
    menu de todo el mundo."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "Includes_Home.xml"), encoding="utf-8") as handle:
        includes = handle.read()
    assert "Window(Home).Property(adviser.ask_ready)" in includes


def test_similares_tambien_es_un_boton_de_la_ficha(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "DialogVideoInfo.xml"), encoding="utf-8") as handle:
        ficha = handle.read()
    assert "?action=similar" in ficha
    assert "String.IsEqual(ListItem.DBType,movie)" in ficha, "el indice es de peliculas"


def test_los_ficheros_nuevos_siguen_siendo_xml_valido(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    for fichero in ("Includes_Home.xml", "DialogVideoInfo.xml"):
        ET.parse(os.path.join(raiz, "xml", fichero))


def test_revienta_si_estuary_ya_no_tiene_los_submenus(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"), con_submenus=False)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)


def test_revienta_si_cambian_los_botones_de_la_ficha(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"), con_ficha=False)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)


def test_el_sufijo_del_parche_acompana_a_la_version_de_estuary():
    """Sin el, dos clones distintos del mismo Estuary se llamarian igual y un
    equipo no sabria que hay uno mas nuevo."""
    assert patch.PATCH_VERSION
    raiz = _estuary_falso(str(__import__("tempfile").mkdtemp()))
    info = patch.apply(raiz)
    assert info["version"] == "4.0.0+" + patch.PATCH_VERSION


def test_actualizar_biblioteca_recibe_en_vez_de_escanear_si_procede(tmp_path):
    """En un nodo suscriptor, escanear las fuentes locales -que son `davs://`- no
    es lo que se quiere: se quiere recibir la biblioteca ya curada."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "MyVideoNav.xml"), encoding="utf-8") as handle:
        nav = handle.read()
    assert "receive_library.py" in nav
    assert "System.AddonIsEnabled(service.nextcloud.sync)" in nav


def test_donde_no_este_ese_complemento_el_boton_hace_lo_de_siempre(tmp_path):
    """No se quita nada: es la leccion de haber desplazado «continuar viendo»."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "MyVideoNav.xml"), encoding="utf-8") as handle:
        nav = handle.read()
    assert "UpdateLibrary(video)" in nav
    assert '!System.AddonIsEnabled(service.nextcloud.sync)">UpdateLibrary' in nav


def test_las_dos_acciones_se_excluyen(tmp_path):
    """Sin condiciones contrarias se ejecutarian las dos, y se escanearia ademas
    de recibir."""
    raiz = _estuary_falso(str(tmp_path / "skin"))
    patch.apply(raiz)
    with open(os.path.join(raiz, "xml", "MyVideoNav.xml"), encoding="utf-8") as handle:
        nav = handle.read()
    assert nav.count("System.AddonIsEnabled(service.nextcloud.sync)") == 2
    assert nav.count("!System.AddonIsEnabled(service.nextcloud.sync)") == 1
    ET.parse(os.path.join(raiz, "xml", "MyVideoNav.xml"))


def test_revienta_si_estuary_cambia_el_boton_de_actualizar(tmp_path):
    raiz = _estuary_falso(str(tmp_path / "skin"), con_actualizar=False)
    with pytest.raises(patch.PatchError):
        patch.apply(raiz)
