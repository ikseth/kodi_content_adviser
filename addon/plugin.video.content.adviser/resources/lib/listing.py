"""De una recomendacion a un elemento que Kodi sabe pintar.

Hay dos clases de elemento y **se distinguen a proposito**:

- Lo que esta en el catalogo apunta al fichero real de la biblioteca y lleva su
  `dbid`, asi que se reproduce, guarda punto de reanudacion y conserva el menu
  contextual de biblioteca.
- Lo que viene de fuera y no se tiene **no se puede reproducir**, y se dice. Un
  elemento que al pulsar no hace nada parece una averia; marcado, es una lista de
  deseos, que si sirve.
"""

import xbmcgui
import xbmcplugin
from adviser.domain.blend import LIBRARY, OUTSIDE

from .bridge import localise, log, rpc

__all__ = ["render", "render_tvshows", "movie_details"]

_DETAIL_FIELDS = ["title", "year", "plot", "rating", "art", "file", "runtime",
                  "genre", "director", "playcount", "resume"]


def movie_details(movie_id):
    result = rpc("VideoLibrary.GetMovieDetails",
                 {"movieid": int(movie_id), "properties": _DETAIL_FIELDS})
    return (result or {}).get("moviedetails")


def _plot_with_reason(plot, because):
    if not because:
        return plot
    motivo = localise(30020) % because
    return "%s\n\n%s" % (motivo, plot) if plot else motivo


def _fill(item, details, plot):
    tag = item.getVideoInfoTag()
    # Los setters de InfoTagVideo llegaron en Kodi 20. El objetivo es Omega (21),
    # pero el manifiesto declara xbmc.python 3.0.0, asi que se comprueba en vez de
    # suponer: si no estan, se cae a `setInfo`, que en 21 esta en desuso.
    if hasattr(tag, "setDbId"):
        tag.setMediaType("movie")
        tag.setDbId(int(details["movieid"]))
        tag.setTitle(details.get("title") or "")
        tag.setPlot(plot)
        if details.get("year"):
            tag.setYear(int(details["year"]))
        if details.get("rating"):
            tag.setRating(float(details["rating"]))
        if details.get("genre"):
            tag.setGenres(list(details["genre"]))
        if details.get("director"):
            tag.setDirectors(list(details["director"]))
        if details.get("playcount") is not None:
            tag.setPlaycount(int(details["playcount"]))
        if details.get("runtime"):
            tag.setDuration(int(details["runtime"]))
    else:  # pragma: no cover - solo en Kodi 19
        item.setInfo("video", {"mediatype": "movie", "dbid": int(details["movieid"]),
                               "title": details.get("title") or "", "plot": plot,
                               "year": details.get("year") or 0})
    art = details.get("art") or {}
    if art:
        item.setArt(art)


def _library_item(movie_id, titles, because):
    details = movie_details(movie_id)
    if not details or not details.get("file"):
        # Una recomendacion que no se puede reproducir es peor que ninguna.
        log("se omite %s: sin fichero reproducible" % movie_id)
        return None
    item = xbmcgui.ListItem(label=details.get("title") or titles.get(str(movie_id), ""))
    item.setProperty("IsPlayable", "true")
    _fill(item, details, _plot_with_reason(details.get("plot") or "", because))
    return details["file"], item


def _outside_item(title):
    """Una obra que no esta en el catalogo. Se marca en el titulo, que es lo unico
    que cualquier piel muestra seguro, y ademas en una propiedad por si la piel
    quiere hacer algo mejor."""
    item = xbmcgui.ListItem(label="%s %s" % (title, localise(30040)))
    item.setProperty("IsPlayable", "false")
    item.setProperty("adviser_outside_catalogue", "true")
    tag = item.getVideoInfoTag()
    if hasattr(tag, "setTitle"):
        tag.setMediaType("movie")
        tag.setTitle(title)
        tag.setPlot(localise(30041))
    return "", item


def render(handle, entries, titles, reasons=None):
    """Pinta un listado.

    `entries` es `[(clase, referencia, titulo)]`, tal como lo devuelve
    `adviser.domain.blend.combine`. `reasons` mapea `dbid -> titulo de la semilla`.
    """
    reasons = reasons or {}
    items = []
    for kind, reference, title in entries:
        if kind == LIBRARY:
            built = _library_item(reference, titles, reasons.get(reference))
        elif kind == OUTSIDE:
            built = _outside_item(title)
        else:  # pragma: no cover - no deberia ocurrir
            log("clase de recomendacion desconocida: %s" % kind)
            built = None
        if built:
            items.append((built[0], built[1], False))

    xbmcplugin.setContent(handle, "movies")
    if items:
        xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    return len(items)


_TVSHOW_FIELDS = ["title", "year", "plot", "rating", "art", "genre", "playcount",
                  "episode", "watchedepisodes"]


def render_tvshows(handle, shows):
    """Series. **Son carpetas, no ficheros**: al abrirlas se entra en la serie,
    que es lo que espera quien la elige, en vez de intentar reproducir algo."""
    items = []
    for show in shows:
        item = xbmcgui.ListItem(label=show.get("title") or "")
        tag = item.getVideoInfoTag()
        if hasattr(tag, "setDbId"):
            tag.setMediaType("tvshow")
            tag.setDbId(int(show["tvshowid"]))
            tag.setTitle(show.get("title") or "")
            tag.setPlot(show.get("plot") or "")
            if show.get("year"):
                tag.setYear(int(show["year"]))
            if show.get("genre"):
                tag.setGenres(list(show["genre"]))
        if show.get("art"):
            item.setArt(show["art"])
        ruta = "videodb://tvshows/titles/%s/" % show["tvshowid"]
        items.append((ruta, item, True))

    xbmcplugin.setContent(handle, "tvshows")
    if items:
        xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    return len(items)
