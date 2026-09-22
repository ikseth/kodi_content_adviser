"""De una frase a una consulta que la biblioteca puede contestar.

Todo lo que el modelo puede devolver **tiene que ser comprobable contra el
catalogo**: generos que existen de verdad, anos, minutos, personas. Nada de
titulos. Asi el peor resultado posible es una consulta que no encuentra nada, y
no una lista de peliculas que no se tienen.

La lista de generos reales se le pasa en el prompt: pedirle que elija de un menu
cerrado es mas fiable que pedirle que acierte el vocabulario del catalogo.
"""

import json

__all__ = ["Query", "build_prompt", "parse_query", "SYSTEM_PROMPT", "QueryError",
           "MEDIA_NAMES"]

SORTS = ("rating", "random", "recent", "runtime")


class QueryError(ValueError):
    pass


SYSTEM_PROMPT = (
    "Eres un traductor entre una persona y el catalogo de cine y series de su "
    "propia casa. Conviertes lo que pide en un filtro.\n"
    "Se te dice QUE clase de obra se busca. Si la persona dice «algo» o no lo "
    "precisa, es de esa clase y no de otra.\n"
    "Respondes SOLO con un objeto JSON, sin texto alrededor y sin bloques de "
    "codigo, con estas claves, todas opcionales:\n"
    '  "genres": generos de los que vale CUALQUIERA. «terror o suspense» va aqui\n'
    '  "genres_all": generos que tienen que darse TODOS a la vez. «terror y '
    'suspense» va aqui\n'
    '  "exclude_genres": lo que hay que evitar\n'
    "Los tres se eligen EXACTAMENTE de la lista de generos que se te da.\n"
    '  "year_from", "year_to": numeros de ano\n'
    '  "max_runtime": minutos como maximo\n'
    '  "people": nombres de directores o interpretes\n'
    '  "sort": uno de rating, random, recent, runtime\n'
    "NUNCA propongas titulos: no sabes cuales tiene esta persona. "
    "Si algo de lo que pide no se puede expresar con esas claves, omitelo.\n"
    "\n"
    "Fijate en la diferencia, que es la que mas se falla:\n"
    '  «algo de terror y suspense» -> {"genres_all": ["Terror", "Suspense"]}\n'
    '  «algo de aventuras o familiar» -> {"genres": ["Aventura", "Familia"]}\n'
    '  «algo de risa» -> {"genres": ["Comedia"]}'
)


class Query:
    """Una consulta estructurada, ya saneada."""

    def __init__(self, genres=None, exclude_genres=None, year_from=None,
                 year_to=None, max_runtime=None, people=None, sort=None,
                 genres_all=None):
        self.genres = genres or []
        self.genres_all = genres_all or []
        self.exclude_genres = exclude_genres or []
        self.year_from = year_from
        self.year_to = year_to
        self.max_runtime = max_runtime
        self.people = people or []
        self.sort = sort

    @property
    def is_empty(self):
        return not any((self.genres, self.genres_all, self.exclude_genres,
                        self.year_from, self.year_to, self.max_runtime, self.people))

    def __eq__(self, other):
        return isinstance(other, Query) and vars(self) == vars(other)

    def __repr__(self):  # pragma: no cover - solo para depurar
        return "Query(%r)" % vars(self)


MEDIA_NAMES = {"movie": "una pelicula", "tvshow": "una serie"}


def build_prompt(request, genres, media_type="movie"):
    """El mensaje del usuario, con el vocabulario real del catalogo delante.

    **Y con que clase de obra se busca.** Sin decirlo, «algo de humor» pedido
    desde las series se traduce igual que desde las peliculas, y el filtro acaba
    aplicandose a lo que toca por casualidad y no por haberlo entendido.
    """
    listado = ", ".join(sorted(genres)) if genres else "(sin generos catalogados)"
    clase = MEDIA_NAMES.get(media_type, MEDIA_NAMES["movie"])
    return ("Se busca %s.\nGeneros disponibles: %s\n\nPeticion: %s"
            % (clase, listado, request))


def _clean_text_list(value, allowed=None):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = []
    lookup = {str(a).strip().lower(): a for a in (allowed or ())}
    for item in value:
        text = " ".join(str(item or "").split())
        if not text:
            continue
        if allowed is not None:
            # Un genero que el catalogo no tiene no filtra nada y ademas seria un
            # invento del modelo colado hasta la pantalla. Se descarta.
            real = lookup.get(text.lower())
            if real is None:
                continue
            text = real
        cleaned.append(text)
    return cleaned


def _clean_int(value, low=None, high=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if low is not None and number < low:
        return None
    if high is not None and number > high:
        return None
    return number


def parse_query(text, genres=()):
    """Convierte la respuesta del modelo en una `Query`, descartando lo que no vale.

    Se tolera que el modelo envuelva el JSON en texto o en un bloque de codigo:
    pasa a menudo y no merece fallar por ello.
    """
    if not text:
        raise QueryError("respuesta vacia")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise QueryError("la respuesta no contiene un objeto JSON")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as error:
        raise QueryError("JSON invalido: %s" % error) from None
    if not isinstance(data, dict):
        raise QueryError("la respuesta no es un objeto")

    sort = data.get("sort")
    sort = sort if sort in SORTS else None

    return Query(
        genres=_clean_text_list(data.get("genres"), genres),
        genres_all=_clean_text_list(data.get("genres_all"), genres),
        exclude_genres=_clean_text_list(data.get("exclude_genres"), genres),
        year_from=_clean_int(data.get("year_from"), 1870, 2200),
        year_to=_clean_int(data.get("year_to"), 1870, 2200),
        max_runtime=_clean_int(data.get("max_runtime"), 1, 1000),
        people=_clean_text_list(data.get("people")),
        sort=sort,
    )
