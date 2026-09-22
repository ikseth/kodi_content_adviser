"""Sugerencias mientras se teclea, sacadas del catalogo propio.

Tres decisiones, y ninguna es de gusto:

1. **Sin acentos, sin mayusculas y sin `ñ`.** Esto se teclea con un mando, en una
   cuadricula de letras. Obligar a acertar la tilde de «Pelicula» es castigar al
   usuario por el teclado que tiene. Lo de la `ñ` se penso al reves al principio
   —es una letra propia, no una `n` con adorno— y se corrigio porque **los modos
   de fallo no son simetricos**: plegarla enseña de mas, no plegarla no enseña
   nada. En un buscador, ensenar de mas es recuperable y no ensenar nada no.

2. **Por prefijo de palabra, no de cadena.** Nadie teclea «La jungla de cristal»
   desde la «L». Teclea «jungla». Una busqueda que solo mire el principio del
   titulo no encuentra casi nada de lo que la gente busca.

3. **Por cubos de dos letras.** Un catalogo real son miles de titulos y decenas de
   miles de nombres. Con una sola letra el cubo mayor se iba al mega, que en una
   Raspberry se nota en cada pulsacion; con dos baja a decenas de kilobytes. El
   precio es que **con una sola letra no se sugiere nada**, y no es un precio: en
   un catalogo de miles de obras, nueve sugerencias sacadas de una inicial no
   ayudan a nadie.
"""

import unicodedata

__all__ = ["PrefixIndex", "TITLE", "PERSON", "normalise", "bucket_key", "MIN_QUERY"]

# Por debajo de esto no se sugiere: una sola letra no distingue nada en un
# catalogo real, y obligaria a mantener cubos enormes para nada.
MIN_QUERY = 2

TITLE = "title"
PERSON = "person"

# Cuanto vale cada clase cuando dos sugerencias empatan. Quien busca en una
# videoteca busca una pelicula mucho mas a menudo que a una persona.
WEIGHTS = {TITLE: 2.0, PERSON: 1.0}

# Palabras que no valen como punto de entrada: nadie busca «de» ni «the».
_STOPWORDS = frozenset((
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "en", "a", "the", "of", "and", "to", "in",
))


def normalise(text):
    """Minusculas y sin marcas diacriticas, incluida la de la `ñ`."""
    if not text:
        return ""
    text = " ".join(str(text).split()).lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def bucket_key(normalised):
    """Cubo al que pertenece un texto ya normalizado."""
    return normalised[:MIN_QUERY]


def _entry_points(normalised):
    """La cadena entera y cada palabra util, para poder buscar por cualquiera."""
    points = {normalised}
    words = normalised.split()
    for position, word in enumerate(words):
        if position and word in _STOPWORDS:
            continue
        points.add(" ".join(words[position:]))
    return points


class PrefixIndex:
    def __init__(self, buckets):
        self._buckets = buckets

    @property
    def size(self):
        return len({term for bucket in self._buckets.values() for _, term, _ in bucket})

    @classmethod
    def build(cls, terms):
        """`terms` es `[(texto, clase)]`. Los repetidos se funden."""
        seen = {}
        for text, kind in terms:
            text = " ".join(str(text or "").split())
            if not text:
                continue
            # Un mismo nombre puede ser titulo y persona; gana la clase que mas
            # pesa, porque es la que decide el orden.
            if text not in seen or WEIGHTS.get(kind, 0) > WEIGHTS.get(seen[text], 0):
                seen[text] = kind

        buckets = {}
        for text, kind in seen.items():
            normalised = normalise(text)
            if not normalised:
                continue
            for point in _entry_points(normalised):
                if len(point) < MIN_QUERY:
                    continue
                buckets.setdefault(bucket_key(point), []).append((point, text, kind))
        return cls(buckets)

    def suggest(self, query, limit=10):
        """Devuelve `[(texto, clase)]`, de mas a menos pertinente."""
        needle = normalise(query)
        if len(needle) < MIN_QUERY:
            return []

        best = {}
        for point, text, kind in self._buckets.get(bucket_key(needle), ()):
            if not point.startswith(needle):
                continue
            # Cuanto mas cerca del principio del termino empiece la coincidencia,
            # mas pertinente es: «jungla» sobre «La jungla de cristal» vale menos
            # que sobre «Jungla de cristal».
            depth = len(normalise(text)) - len(point)
            score = (WEIGHTS.get(kind, 0.0), -depth, -len(text))
            if text not in best or score > best[text][0]:
                best[text] = (score, kind)

        ranked = sorted(best.items(), key=lambda row: (
            -row[1][0][0], -row[1][0][1], -row[1][0][2], normalise(row[0])))
        return [(text, data[1]) for text, data in ranked[:limit]] if limit else \
               [(text, data[1]) for text, data in ranked]

    def to_dict(self):
        return {"version": 1,
                "buckets": {k: [list(row) for row in v] for k, v in self._buckets.items()}}

    @classmethod
    def from_dict(cls, data):
        return cls({k: [tuple(row) for row in v]
                    for k, v in (data.get("buckets") or {}).items()})
