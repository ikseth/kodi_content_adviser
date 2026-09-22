"""De una `Query` a un filtro que Kodi entiende.

Los campos y operadores de aqui **no salen de la documentacion**: se verificaron
contra un Kodi 21 real con `JSONRPC.Introspect`, porque ese enum se genera en
ejecucion y no esta en el esquema publicado.

**«Y» y «o» no son lo mismo, aunque lo pareciesen.** Una regla de genero con
varios valores casa con cualquiera de ellos, asi que «terror o suspense» y
«terror y suspense» daban el mismo resultado. El «y» necesita una regla por
genero, combinadas con `and`.

Un detalle que se paga si se olvida: `greaterthan` y `lessthan` son estrictos.
«Desde 1990» con `greaterthan 1990` se deja fuera 1990 entero, que es justo el ano
que pidio el usuario.

Y otro que ya se pago: **el campo `time` esta en segundos, no en minutos**, aunque
la interfaz de listas inteligentes de Kodi lo pida en minutos. `time lessthan 106`
no devuelve las peliculas de menos de 106 minutos: devuelve las que duran menos de
106 **segundos**, que es casi ninguna. Hay que pedir `time lessthan 6360`.

Sin convertir no falla, que seria mejor: contesta casi nada, y eso parece un
catalogo pobre en vez de un error.
"""

SECONDS_PER_MINUTE = 60

__all__ = ["to_library_filter", "to_sort"]

_SORTS = {
    "rating": {"method": "rating", "order": "descending"},
    "random": {"method": "random"},
    "recent": {"method": "dateadded", "order": "descending"},
    "runtime": {"method": "runtime", "order": "ascending"},
}


def to_library_filter(query):
    """Devuelve el filtro para `VideoLibrary.GetMovies`, o `None` si no hay nada."""
    rules = []

    if query.genres:
        # Una lista de valores con `is` significa **cualquiera de ellos**: es el
        # «o». Para el «y» no vale, porque una sola regla no puede exigir dos
        # generos a la vez; hacen falta dos reglas.
        rules.append({"field": "genre", "operator": "is", "value": list(query.genres)})
    for genero in query.genres_all:
        rules.append({"field": "genre", "operator": "is", "value": genero})
    if query.exclude_genres:
        rules.append({"field": "genre", "operator": "isnot",
                      "value": list(query.exclude_genres)})

    if query.year_from is not None and query.year_to is not None:
        rules.append({"field": "year", "operator": "between",
                      "value": [str(query.year_from), str(query.year_to)]})
    elif query.year_from is not None:
        rules.append({"field": "year", "operator": "greaterthan",
                      "value": str(query.year_from - 1)})
    elif query.year_to is not None:
        rules.append({"field": "year", "operator": "lessthan",
                      "value": str(query.year_to + 1)})

    if query.max_runtime is not None:
        limit = (query.max_runtime + 1) * SECONDS_PER_MINUTE
        rules.append({"field": "time", "operator": "lessthan", "value": str(limit)})

    if query.people:
        # Una persona puede dirigir o actuar, y quien pregunta rara vez lo
        # distingue. Se acepta cualquiera de las dos.
        alternatives = []
        for name in query.people:
            alternatives.append({"field": "actor", "operator": "contains", "value": name})
            alternatives.append({"field": "director", "operator": "contains", "value": name})
        rules.append({"or": alternatives})

    if not rules:
        return None
    if len(rules) == 1:
        return rules[0]
    return {"and": rules}


def to_sort(query):
    """Orden pedido, o `None` para dejar el de Kodi."""
    return dict(_SORTS[query.sort]) if query.sort in _SORTS else None
