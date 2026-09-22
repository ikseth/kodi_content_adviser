"""Mezcla del motor local con una fuente externa.

Sale de una medida, no de una preferencia: el motor local tiene respuesta
confiable para **entre un quinto y un tercio** del catalogo —las obras que
comparten coleccion, director o reparto— y ruido para el resto. La fuente externa
mantiene la coherencia hasta el final, pero **buena parte de lo que propone no esta
en el catalogo**: en una muestra real, 4 de cada 8 no se podian reproducir.

No compiten, se complementan, y de ahi las reglas de aqui:

1. **Lo local manda.** Ya paso el umbral de confianza y ademas se puede reproducir.
2. **Lo externo que resulta que tienes sube a reproducible.** Es el caso mas
   valioso de todos: una obra de tu catalogo que el motor local no relaciono y la
   fuente externa si. Deja de ser una recomendacion muerta y pasa a ser una
   pelicula que puedes poner.
3. **Lo externo que no tienes se marca, o no se ensena.** Ofrecer algo que al
   pulsar no hace nada es peor que no ofrecerlo; decirlo claro lo convierte en una
   lista de deseos, que si sirve.
"""

__all__ = ["combine", "LIBRARY", "OUTSIDE"]

LIBRARY = "library"
OUTSIDE = "outside"


def combine(local, external, wanted, resolve, exclude=(), include_outside=True):
    """Devuelve `[(clase, referencia, titulo)]` hasta `wanted` elementos.

    `local` es `[(dbid, puntuacion)]`; `external`, `[(id_externo, titulo)]` en el
    orden que dio la fuente; `resolve(id_externo)` devuelve el `dbid` de esa obra
    en el catalogo, o `None` si no se tiene.

    Para lo local el titulo es `None`: ya lo sabe la biblioteca. Para lo de fuera
    es lo unico que hay.
    """
    skip = set(exclude)
    result = []

    for dbid, _score in local:
        if dbid in skip:
            continue
        skip.add(dbid)
        result.append((LIBRARY, dbid, None))
        if wanted and len(result) >= wanted:
            return result

    for reference, title in external:
        dbid = resolve(reference)
        if dbid is not None:
            if dbid in skip:
                continue
            skip.add(dbid)
            result.append((LIBRARY, dbid, None))
        else:
            if not include_outside:
                continue
            result.append((OUTSIDE, reference, title))
        if wanted and len(result) >= wanted:
            break

    return result
