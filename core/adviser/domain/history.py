"""De lo ultimo visto a una fila de recomendaciones.

Dos cosas que se midieron sobre una biblioteca grande y que mandan sobre
este modulo:

1. **`lastplayed` se rellena aunque `playcount` sea 0.** Hay peliculas con fecha de
   hoy y cuenta cero: se empezaron y se dejaron. «Visto» y «empezado» no son lo
   mismo, y tomar lo abandonado como senal de gusto puede recomendar justo lo
   contrario de lo que el espectador quiere. Por eso lo inacabado **no entra por
   defecto**, y cuando entra lo hace con menos peso.

2. **Con biblioteca MySQL compartida, el historial es de la casa, no del equipo.**
   El motor no puede arreglarlo. Lo que si puede es no prometer lo que no cumple:
   esto es «parecido a lo ultimo visto», no «te conocemos».
"""

from ..identity import item_id as resolve_id

__all__ = ["recent_seeds", "recommend_from_history", "DEFAULT_SEEDS",
           "DEFAULT_MIN_SCORE", "DEFAULT_MAX_PER_SEED"]

DEFAULT_SEEDS = 10

# Cuanto pesa una semilla segun su antiguedad. La ultima vista manda mas que la
# decima, pero no tanto como para que la fila sea un monocultivo de una sola obra.
_DECAY = 0.85

# Lo empezado y no acabado, cuando se admite, entra a la mitad.
_UNFINISHED_WEIGHT = 0.5

# Umbral de confianza de referencia. **Es un punto de partida ajustable, no una
# verdad**: sale de medir la curva sobre un catalogo de varios miles de peliculas.
#
#     umbral 0,05 -> 6,6 resultados por fila,  6 % de filas vacias
#     umbral 0,10 -> 3,6 resultados por fila, 25 % de filas vacias
#     umbral 0,15 -> 3,3 resultados por fila, 29 % de filas vacias
#     umbral 0,30 -> 2,9 resultados por fila, 34 % de filas vacias
#
# La curva tiene un codo en 0,10: por debajo se rellena con ruido (6,6 resultados
# y casi ninguna fila vacia porque entra cualquier cosa), y por encima se pierden
# filas sin ganar casi calidad. Por eso 0,10 y no 0,15 ni 0,30.
DEFAULT_MIN_SCORE = 0.10

# Cuantos huecos puede ocupar una misma semilla. Medido sobre la misma fila real:
#
#     sin tope -> 2 semillas distintas de 10; una ocupa 7 huecos
#     tope 3   -> 4 semillas distintas
#     tope 2   -> 5 semillas distintas
#     tope 1   -> 10 semillas distintas, pero rellena con coincidencias flojas
#
# 2 es el equilibrio: deja ver una saga sin que se coma la fila. El monocultivo no
# lo causaban los duplicados —deduplicando, una sola semilla seguia ocupando 7 de
# 10 huecos—, asi que este tope es necesario aunque el catalogo este limpio.
DEFAULT_MAX_PER_SEED = 2


def recent_seeds(items, limit=DEFAULT_SEEDS, include_unfinished=False):
    """Las ultimas obras reproducidas, de mas a menos reciente.

    Devuelve `[(id, peso)]`. Un item sin `lastplayed` no ha sido tocado nunca y no
    entra, tenga la cuenta que tenga. Uno sin identificador tampoco, porque una
    semilla sin identificador no es una semilla: es una fila vacia sin aviso.
    """
    candidates = []
    for item in items:
        stamp = item.get("lastplayed")
        if not stamp:
            continue
        finished = bool(item.get("playcount"))
        if not finished and not include_unfinished:
            continue
        identifier = resolve_id(item)
        if identifier is None:
            continue
        candidates.append((stamp, identifier, finished))
    candidates.sort(reverse=True)

    seeds = []
    for position, (_, item_id, finished) in enumerate(candidates[:limit]):
        weight = _DECAY ** position
        if not finished:
            weight *= _UNFINISHED_WEIGHT
        seeds.append((item_id, weight))
    return seeds


def recommend_from_history(index, seeds, limit=20, exclude=(), per_seed=40,
                           min_score=DEFAULT_MIN_SCORE,
                           max_per_seed=DEFAULT_MAX_PER_SEED,
                           key_of=None):
    """Mezcla los vecinos de varias semillas en una sola lista ordenada.

    Se suma la aportacion de cada semilla en vez de quedarse con el maximo: asi una
    obra que se parece un poco a cinco de las ultimas diez sube por encima de otra
    que se parece mucho a una sola. Es lo que distingue una fila «porque viste
    esto» de diez filas pegadas.

    Sumar no basta, y esta medido: una semilla con una saga detras puntua el doble
    que las demas y se lleva la fila entera. De ahi `max_per_seed`.

    `key_of(item_id)` devuelve la identidad real de una obra —su `uniqueid` cuando
    lo hay, y si no titulo y ano normalizados— para que una pelicula catalogada dos
    veces no salga dos veces, ni se recomiende a si misma desde su propio duplicado.
    Devolver `None` desactiva la deduplicacion de ese item.
    """
    skip = set(exclude)
    skip.update(item_id for item_id, _ in seeds)

    totals = {}
    reasons = {}
    for item_id, weight in seeds:
        for other_id, score in index.neighbours(item_id, limit=per_seed, exclude=skip,
                                                min_score=min_score):
            contribution = score * weight
            totals[other_id] = totals.get(other_id, 0.0) + contribution
            best = reasons.get(other_id)
            if best is None or contribution > best[1]:
                reasons[other_id] = (item_id, contribution)

    ranked = [(other_id, total, reasons[other_id][0]) for other_id, total in totals.items()]
    ranked.sort(key=lambda row: (-row[1], row[0]))

    # Las semillas tambien se deduplican: si no, una obra catalogada dos veces se
    # recomienda a si misma, que fue exactamente lo que se vio con datos reales.
    seen_keys = set()
    if key_of is not None:
        for item_id, _ in seeds:
            key = key_of(item_id)
            if key is not None:
                seen_keys.add(key)

    used = {}
    chosen = []
    for other_id, total, because in ranked:
        if key_of is not None:
            key = key_of(other_id)
            if key is not None:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
        if max_per_seed and used.get(because, 0) >= max_per_seed:
            continue
        used[because] = used.get(because, 0) + 1
        chosen.append((other_id, total, because))
        if limit and len(chosen) >= limit:
            break
    return chosen
