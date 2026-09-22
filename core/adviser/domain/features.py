"""De un item de la videoteca a una bolsa de rasgos con peso.

Cada rasgo lleva delante su espacio de nombres (`genre:`, `director:`…) para que
un estudio y un genero que se llamen igual no se confundan.

Los pesos por espacio no sustituyen al idf: lo acompanan. El idf dice **cuanto
distingue** un rasgo dentro de este catalogo concreto; el peso dice **cuanto nos
fiamos** de ese tipo de rasgo. Compartir coleccion es mejor senal que compartir
genero aunque en una videoteca de peliculas de accion "accion" sea raro.
"""

__all__ = ["FeatureExtractor", "DEFAULT_WEIGHTS"]

DEFAULT_WEIGHTS = {
    "set": 3.0,        # misma coleccion: la senal mas fuerte que da la biblioteca
    "director": 2.0,
    "actor": 1.5,
    "genre": 1.0,
    "studio": 0.7,
    "country": 0.5,
    "decade": 0.5,
}

# Cuantos interpretes se toman de la ficha. El reparto viene ordenado por
# importancia; la cola son papeles menores que solo anaden ruido y tamano.
DEFAULT_CAST_DEPTH = 10


def _clean(value):
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = " ".join(text.split()).lower()
    return text or None


class FeatureExtractor:
    def __init__(self, weights=None, cast_depth=DEFAULT_CAST_DEPTH):
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)
        self.cast_depth = cast_depth

    def _weight(self, namespace):
        return self.weights.get(namespace, 1.0)

    def extract(self, item):
        """Devuelve `{rasgo: peso}` para un item de la videoteca.

        Tolera fichas incompletas a proposito: un item sin reparto o sin estudio
        sigue siendo indexable con lo que tenga. Degradar es preferible a excluir.
        """
        features = {}

        def add(namespace, value):
            text = _clean(value)
            if text:
                features["%s:%s" % (namespace, text)] = self._weight(namespace)

        for namespace, key in (("genre", "genre"), ("director", "director"),
                               ("studio", "studio"), ("country", "country")):
            values = item.get(key) or []
            if isinstance(values, str):
                values = [values]
            for value in values:
                add(namespace, value)

        add("set", item.get("set"))

        year = item.get("year")
        if isinstance(year, int) and year > 0:
            add("decade", "%ds" % (year // 10 * 10))

        for member in (item.get("cast") or [])[:self.cast_depth]:
            add("actor", member.get("name") if isinstance(member, dict) else member)

        return features
