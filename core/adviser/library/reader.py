"""Lectura paginada de la videoteca por JSON-RPC.

**Nunca se lee el fichero de base de datos.** En un equipo cuya biblioteca vive en
MySQL no hay ninguna `MyVideos*.db` que leer. JSON-RPC
es la unica via que funciona en los dos casos, y ademas devuelve nombres de campo
estables en vez de las columnas posicionales `cNN`, que cambian entre versiones.

**Dos fases, y el reparto sale de una medida, no de una intuicion.** Sobre un catalogo
de varios miles de peliculas, en una Raspberry Pi 4 con la biblioteca en MySQL:

    solo title                       1,93 s
    title + genre + director         2,03 s   (+0,10 s)
    title + uniqueid                14,21 s   (+12,28 s)
    title + cast                    31,10 s   (+29,17 s)

`uniqueid` mueve 0,2 MB y tarda 12 s: **el coste son las idas y vueltas, no los
bytes**. De ahi que el indice basico sea utilizable en segundos y el enriquecido
vaya aparte, en segundo plano.
"""

__all__ = ["LibraryReader", "BASIC_MOVIE_FIELDS", "RICH_MOVIE_FIELDS",
           "BASIC_TVSHOW_FIELDS", "RICH_TVSHOW_FIELDS"]

# Fase 1. Todo lo de aqui esta medido como practicamente gratis incluso en el
# equipo mas lento. Anadir un campo a esta lista exige volver a medirlo alli.
BASIC_MOVIE_FIELDS = ("title", "year", "genre", "director", "studio", "country", "set")

# Fase 2. Cara: se construye en segundo plano y nunca en un camino de interfaz.
RICH_MOVIE_FIELDS = ("cast", "uniqueid")

BASIC_TVSHOW_FIELDS = ("title", "year", "genre", "studio")
RICH_TVSHOW_FIELDS = ("cast", "uniqueid")

_MEDIA = {
    "movie": ("VideoLibrary.GetMovies", "movies", "movieid"),
    "tvshow": ("VideoLibrary.GetTVShows", "tvshows", "tvshowid"),
}


class LibraryReader:
    """Lee la videoteca a traves de un transporte JSON-RPC.

    `call(method, params) -> result` es lo unico que se le pide al transporte. Asi
    el nucleo sirve igual dentro de Kodi (`xbmc.executeJSONRPC`) que fuera (HTTP),
    y se puede probar con un transporte falso.
    """

    def __init__(self, call, page_size=500):
        if page_size < 1:
            raise ValueError("page_size debe ser positivo")
        self._call = call
        self._page_size = page_size

    def read(self, media_type, fields):
        """Devuelve la lista completa de items del tipo pedido.

        Se pagina **por memoria, no por tiempo**: medido, paginar de 200 en vez de
        500 no mejora el tiempo (51,61 s frente a 50,86 s). Lo que acota es el pico
        de memoria, que es el problema real en un equipo pequeno.
        """
        try:
            method, key, id_key = _MEDIA[media_type]
        except KeyError:
            raise ValueError("tipo de medio desconocido: %r" % (media_type,)) from None

        items = []
        start = 0
        while True:
            result = self._call(method, {
                "properties": list(fields),
                "limits": {"start": start, "end": start + self._page_size},
            }) or {}
            page = result.get(key) or []
            items.extend(page)
            total = (result.get("limits") or {}).get("total")
            if not page:
                break
            if total is not None and len(items) >= total:
                break
            start += self._page_size
        for item in items:
            item.setdefault("id", item.get(id_key))
            item.setdefault("media_type", media_type)
        return items

    def count(self, media_type):
        method, _, _ = _MEDIA[media_type]
        result = self._call(method, {"limits": {"start": 0, "end": 1}}) or {}
        return (result.get("limits") or {}).get("total", 0)
