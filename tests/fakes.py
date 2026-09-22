"""Transporte JSON-RPC falso. Responde como Kodi sin necesitar Kodi."""


class FakeTransport:
    def __init__(self, items_by_method):
        self._items = items_by_method
        self.calls = []

    def __call__(self, method, params=None):
        self.calls.append((method, params))
        key = {"VideoLibrary.GetMovies": "movies",
               "VideoLibrary.GetTVShows": "tvshows"}[method]
        items = self._items.get(method, [])
        limits = (params or {}).get("limits") or {}
        start = limits.get("start", 0)
        end = limits.get("end", len(items))
        return {key: items[start:end],
                "limits": {"start": start, "end": min(end, len(items)), "total": len(items)}}


def movie(movie_id, **fields):
    item = {"movieid": movie_id, "title": "Pelicula %d" % movie_id}
    item.update(fields)
    return item
