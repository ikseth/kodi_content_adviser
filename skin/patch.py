"""El clon de Estuary, expresado como parche.

**No se mantiene un skin: se mantiene un diff.** Kodi no tiene herencia de skins,
asi que anadir una fila a la pantalla de inicio obliga a una copia completa. Una
copia, abandonada a su suerte, deja de recibir las mejoras y traducciones de
Estuary y se rompe en cada version mayor de Kodi (`xbmc.gui` va 5.16.0 en Nexus,
5.17.0 en Omega y 5.18.0 en la rama siguiente).

La salida es esta: **el clon se genera cada vez, a partir del Estuary de la version
de Kodi que se tenga delante**, aplicando unas pocas decenas de lineas. Subir de
Kodi pasa a ser «regenerar y probar», no «rebasar un skin».

Por eso cada cambio se ancla en un texto exacto y **revienta si no lo encuentra**.
Un parche que aplica a medias y calla es peor que uno que falla: dejaria un skin
sin la fila y sin ningun aviso.
"""

import os
import re

__all__ = ["apply", "PatchError", "SKIN_ID", "SOURCE_ID"]

SOURCE_ID = "skin.estuary"
SKIN_ID = "skin.estuary.adviser"
SKIN_NAME = "Estuary Adviser"
ADVISER_ID = "plugin.video.content.adviser"

# Los fragmentos son XML y viven como XML, no metidos en una cadena de Python:
# asi se leen, se comparan y se editan con las mismas herramientas que el skin.
FRAGMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fragments")


def _fragment(name):
    with open(os.path.join(FRAGMENTS, name), encoding="utf-8") as handle:
        return handle.read()


# La fila solo existe si el complemento esta instalado y activo. Es el mismo
# idioma que usa Estuary para su propio autocompletado, y evita tener que anadir
# un ajuste de skin: desactivar el complemento retira la fila.
WIDGET = _fragment("widget_home_movies.xml")

# Ancla: el widget de «continuar viendo». La fila se inserta **detras de el**.
#
# Al principio iba detras del de categorias, o sea la primera con contenido, y
# estaba mal: continuar una pelicula a medias es mas urgente que una
# recomendacion, y quien la tenia arriba la echo de menos. Una fila nueva no se
# pone por delante de algo que el usuario ya usaba.
ANCHOR = _fragment("anchor_home_movies.xml")

# El teclado virtual de Kodi ya tiene panel de sugerencias, pero Estuary consulta
# **un id escrito a fuego**: `plugin.program.autocompletion`. Sin clonar el skin,
# la unica forma de alimentarlo seria ocupar ese id, con el choque que eso supone
# con el complemento oficial. Clonado, basta con anadir un valor delante.
#
# Se anade, no se sustituye: las variables de Kodi evaluan sus valores en orden y
# gana el primero cuya condicion se cumpla. Asi, **si el recomendador se desactiva,
# vuelve el comportamiento original de Estuary** en vez de quedarse sin teclado
# predictivo.
KEYBOARD_ANCHOR = _fragment("anchor_variables_autocomplete.xml")
KEYBOARD_VALUE = _fragment("value_variables_autocomplete.xml")

# Estuary ya anade entradas propias al widget de categorias, condicionadas a que
# cierto complemento este activo. Se usa el mismo sitio y el mismo idioma: el
# usuario no tiene por que bajar a «Complementos de video» para preguntar.
SUBMENU = (
    ("anchor_home_movie_submenu.xml", "item_home_movie_submenu.xml"),
    ("anchor_home_tvshow_submenu.xml", "item_home_tvshow_submenu.xml"),
)

# Y el mismo «Similares a esta» del menu contextual, tambien como boton en la
# ficha, al lado de «Reproducir» y «Trailer». Un usuario que abre la ficha no
# tiene por que saber que existe un menu contextual.
INFO_ANCHOR = _fragment("anchor_info_dialog_button.xml")
INFO_BUTTON = _fragment("button_info_dialog.xml")

# En un nodo suscriptor de `kodi-addon-nextcloud`, «actualizar biblioteca» hace
# lo que no toca: escanear las fuentes locales, que ahi son `davs://` y van
# lentas, cuando lo que se quiere es **recibir la biblioteca ya curada** por el
# publicador. Asi que en esos equipos el boton pasa a hacer eso.
#
# Se anade delante y con condicion, **no se sustituye**: donde ese complemento no
# este, el boton sigue haciendo exactamente lo de siempre. Kodi evalua los
# `onclick` en orden y ejecuta los que cumplen su condicion.
UPDATE_ANCHOR = _fragment("anchor_update_library.xml")
UPDATE_ONCLICK = _fragment("onclick_update_library.xml")


class PatchError(RuntimeError):
    pass


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _patch_manifest(path, version_suffix):
    text = _read(path)
    if 'id="%s"' % SOURCE_ID not in text:
        raise PatchError("%s no parece el addon.xml de %s" % (path, SOURCE_ID))

    version = re.search(r'<addon[^>]* version="([^"]+)"', text)
    if not version:
        raise PatchError("no se pudo leer la version de %s" % path)
    upstream = version.group(1)

    text = text.replace('id="%s"' % SOURCE_ID, 'id="%s"' % SKIN_ID, 1)
    text = text.replace('name="Estuary"', 'name="%s"' % SKIN_NAME, 1)
    text = text.replace('version="%s"' % upstream,
                        'version="%s+%s"' % (upstream, version_suffix), 1)
    _write(path, text)
    return upstream


def _patch_home(path):
    text = _read(path)
    if ANCHOR not in text:
        raise PatchError(
            "Estuary ha cambiado: no se encuentra el widget de categorias de peliculas "
            "en %s. Hay que revisar el ancla del parche antes de seguir." % path)
    if WIDGET in text:
        raise PatchError("el parche ya estaba aplicado en %s" % path)

    # Se inserta detras del bloque del ancla, no dentro: se busca el cierre del
    # <include> que abre el ancla.
    start = text.index(ANCHOR)
    close = text.index("</include>\n", start) + len("</include>\n")
    _write(path, text[:close] + WIDGET + text[close:])


def _patch_keyboard(path):
    text = _read(path)
    if KEYBOARD_ANCHOR not in text:
        raise PatchError(
            "Estuary ha cambiado: no se encuentra AutoCompletionContentVar en %s. "
            "Hay que revisar el ancla del parche antes de seguir." % path)
    if KEYBOARD_VALUE in text:
        raise PatchError("el parche del teclado ya estaba aplicado en %s" % path)
    start = text.index(KEYBOARD_ANCHOR) + len(KEYBOARD_ANCHOR)
    _write(path, text[:start] + KEYBOARD_VALUE + text[start:])


def _insert_after(path, anchor, addition, what):
    text = _read(path)
    if anchor not in text:
        raise PatchError(
            "Estuary ha cambiado: no se encuentra %s en %s. Hay que revisar el "
            "ancla del parche antes de seguir." % (what, path))
    if addition in text:
        raise PatchError("el parche de %s ya estaba aplicado en %s" % (what, path))
    start = text.index(anchor) + len(anchor)
    _write(path, text[:start] + addition + text[start:])


def _patch_submenus(path):
    for anchor_name, item_name in SUBMENU:
        _insert_after(path, _fragment(anchor_name), _fragment(item_name),
                      "el submenu de %s" % anchor_name.split("_")[2])


def _patch_info_dialog(path):
    _insert_after(path, INFO_ANCHOR, INFO_BUTTON, "los botones de la ficha")
    # El boton anterior tenia el foco a su izquierda; ahora el ultimo es el
    # nuestro. Sin esto, moverse a la izquierda desde la valoracion se lo salta.
    text = _read(path)
    viejo = "<onleft>441</onleft>"
    if viejo in text:
        _write(path, text.replace(viejo, "<onleft>442</onleft>", 1))


# **Se sube a mano cuando cambia el parche.** El clon hereda la version de
# Estuary, asi que sin este sufijo dos clones distintos del mismo Estuary se
# llamarian igual, y un equipo no tendria forma de saber que hay uno mas nuevo.
PATCH_VERSION = "adviser.3"


def _patch_update_library(path):
    text = _read(path)
    if UPDATE_ANCHOR not in text:
        raise PatchError(
            "Estuary ha cambiado: no se encuentra el boton de actualizar "
            "biblioteca en %s." % path)
    if UPDATE_ONCLICK in text:
        raise PatchError("el parche de actualizar biblioteca ya estaba aplicado")
    # Delante del original, y el original queda con la condicion contraria para
    # que no se ejecuten los dos.
    original = UPDATE_ANCHOR.replace(
        "<onclick>UpdateLibrary(video)</onclick>",
        '<onclick condition="!System.AddonIsEnabled(service.nextcloud.sync)">'
        "UpdateLibrary(video)</onclick>")
    _write(path, text.replace(UPDATE_ANCHOR, UPDATE_ONCLICK + original, 1))


def apply(skin_dir, version_suffix=PATCH_VERSION):
    """Convierte una copia de Estuary en el clon. Modifica `skin_dir` en el sitio."""
    manifest = os.path.join(skin_dir, "addon.xml")
    home = os.path.join(skin_dir, "xml", "Home.xml")
    variables = os.path.join(skin_dir, "xml", "Variables.xml")
    includes = os.path.join(skin_dir, "xml", "Includes_Home.xml")
    info = os.path.join(skin_dir, "xml", "DialogVideoInfo.xml")
    navigation = os.path.join(skin_dir, "xml", "MyVideoNav.xml")
    for path in (manifest, home, variables, includes, info, navigation):
        if not os.path.exists(path):
            raise PatchError("falta %s: %s no parece una copia de Estuary"
                             % (path, skin_dir))
    upstream = _patch_manifest(manifest, version_suffix)
    _patch_home(home)
    _patch_keyboard(variables)
    _patch_submenus(includes)
    _patch_info_dialog(info)
    _patch_update_library(navigation)
    return {"upstream_version": upstream, "skin_id": SKIN_ID,
            "version": "%s+%s" % (upstream, version_suffix)}
