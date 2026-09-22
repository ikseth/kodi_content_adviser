"""Fuente externa de recomendaciones, a traves de TMDb Helper.

**No se reimplementa un cliente de TMDB.** `plugin.video.themoviedb.helper` esta en
el repositorio oficial de Kodi, lleva anos en uso y ya expone las recomendaciones
como un listado. Reescribir eso seria mantener una clave de API, una cache y un
cliente HTTP para llegar al mismo sitio.

**Se pide `recommendations`, nunca `similar`.** Medido sobre la misma pelicula:
`recommendations` devuelve la saga y sus vecinos evidentes; `similar` devuelve
obras sin ninguna relacion. Es un defecto del endpoint de TMDB, no del complemento.

Esta via **solo se usa en «similares a esta»**, que es una peticion explicita del
espectador y admite esperar un segundo. La fila de inicio no la usa: serian tantas
consultas de red como semillas, y esa fila tiene que pintarse ya.
"""

import xbmc

from .bridge import log, rpc

HELPER_ID = "plugin.video.themoviedb.helper"
PATH = "plugin://%s/?info=recommendations&tmdb_type=%%s&tmdb_id=%%s" % HELPER_ID

__all__ = ["available", "installed", "offer_install", "recommendations", "HELPER_ID"]


def installed():
    """Si el complemento esta presente, aunque este desactivado."""
    result = rpc("Addons.GetAddonDetails", {"addonid": HELPER_ID, "properties": ["enabled"]})
    return bool((result or {}).get("addon"))


def available():
    result = rpc("Addons.GetAddonDetails", {"addonid": HELPER_ID, "properties": ["enabled"]})
    return bool(((result or {}).get("addon") or {}).get("enabled"))


def offer_install():
    """Pide a Kodi que instale la fuente externa desde el repositorio oficial.

    **No se declara como dependencia del addon.** Verificado en el codigo de Kodi
    (`AddonInstaller.cpp`): una dependencia `optional="true"` **no se instala
    sola** —la condicion es `(!haveInstalledAddon && !optional)`—, y una
    obligatoria si, pero entonces arrastra diez modulos mas, exige red y clave, y
    contradice lo que este addon promete: funcionar sin red y sin cuentas. Peor
    aun, si el usuario tuviera una version vieja que no se pudiera actualizar,
    **nuestra propia instalacion fallaria**.

    Asi que se ofrece, que es el idioma que usa el propio Estuary con YouTube en
    su dialogo de busqueda.
    """
    xbmc.executebuiltin("InstallAddon(%s)" % HELPER_ID)


def recommendations(tmdb_id, media_type="movie", limit=20):
    """Devuelve `[(id_tmdb, titulo)]`, en el orden en que los da la fuente."""
    result = rpc("Files.GetDirectory",
                 {"directory": PATH % (media_type, tmdb_id), "media": "video",
                  "properties": ["title", "uniqueid"]})
    if not result:
        log("la fuente externa no respondio para tmdb=%s" % tmdb_id, xbmc.LOGWARNING)
        return []
    rows = []
    for entry in (result.get("files") or []):
        reference = (entry.get("uniqueid") or {}).get("tmdb")
        if reference is None:
            # La ultima entrada suele ser «Pagina siguiente», que no es una obra.
            continue
        rows.append((str(reference), entry.get("label") or ""))
        if limit and len(rows) >= limit:
            break
    return rows
