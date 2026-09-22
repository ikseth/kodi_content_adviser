"""Como se identifica un item de la videoteca.

Kodi no usa una clave uniforme: una pelicula es `movieid`, una serie `tvshowid` y
un episodio `episodeid`. `LibraryReader` normaliza eso a `id`, pero el resto del
nucleo no puede **dar por hecho** que le llegue ya normalizado: cuando no llegaba,
el modulo de historial producia semillas `None` sin quejarse, y la fila salia vacia
sin un solo error. Un identificador ausente tiene que ser visible, no silencioso.
"""

__all__ = ["item_id", "ID_KEYS"]

ID_KEYS = ("id", "movieid", "tvshowid", "episodeid", "musicvideoid")


def item_id(item):
    """Identificador del item, o `None` si la ficha no trae ninguno."""
    for key in ID_KEYS:
        value = item.get(key)
        if value is not None:
            return value
    return None
