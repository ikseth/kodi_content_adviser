"""Indice invertido con pesos, y consulta de vecinos por coseno.

**Los vecinos se calculan al preguntar, no por adelantado.** Precalcular la matriz
completa serian millones de pares, minutos de CPU en una Raspberry para un
resultado que caduca en cuanto cambia la biblioteca. Una consulta suelta recorre
solo las listas de los rasgos del item: milisegundos. Y la fila de inicio son diez
consultas, no cuatro mil.
"""

import math

from ..identity import item_id as resolve_id

__all__ = ["SimilarityIndex"]

# Guarda de coste, no de calidad: el idf ya hunde los rasgos omnipresentes. Un
# rasgo en el 60 % del catalogo aporta poco y obliga a recorrer 60 % de las listas
# en cada consulta. Se descarta al construir para que las normas sean coherentes.
DEFAULT_MAX_DOCUMENT_RATIO = 0.35

# ...pero la guarda es sobre la **longitud** de la lista, no sobre su proporcion.
# Una lista de unas decenas nunca es un problema de coste, y descartarla en un
# catalogo pequeno solo destruye senal: con 3 peliculas, cualquier rasgo que
# compartan dos supera el 35 % y desapareceria justo el parecido que buscamos.
MIN_POSTINGS_FLOOR = 50


class SimilarityIndex:
    def __init__(self, postings, vectors, norms, total):
        self._postings = postings
        self._vectors = vectors
        self._norms = norms
        self._total = total

    @property
    def size(self):
        return len(self._vectors)

    @classmethod
    def build(cls, items, extractor, max_document_ratio=DEFAULT_MAX_DOCUMENT_RATIO,
              min_postings_floor=MIN_POSTINGS_FLOOR):
        raw = {}
        frequency = {}
        for item in items:
            identifier = resolve_id(item)
            if identifier is None:
                continue
            features = extractor.extract(item)
            if not features:
                continue
            raw[identifier] = features
            for feature in features:
                frequency[feature] = frequency.get(feature, 0) + 1

        total = len(raw)
        if not total:
            return cls({}, {}, {}, 0)

        ceiling = max(min_postings_floor, int(total * max_document_ratio))
        idf = {
            feature: math.log(1.0 + total / float(count))
            for feature, count in frequency.items()
            if count <= ceiling
        }

        postings = {}
        vectors = {}
        norms = {}
        for item_id, features in raw.items():
            vector = {}
            for feature, weight in features.items():
                scale = idf.get(feature)
                if scale is None:
                    continue
                vector[feature] = weight * scale
            if not vector:
                continue
            vectors[item_id] = vector
            norms[item_id] = math.sqrt(sum(v * v for v in vector.values())) or 1.0
            for feature, value in vector.items():
                postings.setdefault(feature, []).append((item_id, value))
        return cls(postings, vectors, norms, total)

    def features_of(self, item_id):
        return self._vectors.get(item_id)

    def neighbours(self, item_id, limit=20, exclude=(), min_score=0.0):
        """Vecinos de un item que ya esta en el indice.

        `min_score` es el umbral de confianza. El indice no impone ninguno por
        defecto: la politica es de quien pregunta, porque un umbral util aqui no
        tiene por que serlo en otro catalogo.
        """
        vector = self._vectors.get(item_id)
        if not vector:
            return []
        skip = set(exclude)
        skip.add(item_id)
        return self._score(vector, self._norms[item_id], limit, skip, min_score)

    def neighbours_of(self, vector, limit=20, exclude=(), min_score=0.0):
        """Vecinos de un vector cualquiera, aunque no este indexado."""
        if not vector:
            return []
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        return self._score(vector, norm, limit, set(exclude), min_score)

    def _score(self, vector, norm, limit, skip, min_score=0.0):
        totals = {}
        for feature, value in vector.items():
            for other_id, other_value in self._postings.get(feature, ()):
                if other_id in skip:
                    continue
                totals[other_id] = totals.get(other_id, 0.0) + value * other_value
        scored = [
            (other_id, accumulated / (norm * self._norms[other_id]))
            for other_id, accumulated in totals.items()
        ]
        if min_score > 0.0:
            scored = [pair for pair in scored if pair[1] >= min_score]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:limit] if limit else scored

    def to_dict(self):
        return {
            "version": 1,
            "total": self._total,
            "vectors": {str(k): v for k, v in self._vectors.items()},
        }

    @classmethod
    def from_dict(cls, data):
        vectors = {}
        for key, vector in (data.get("vectors") or {}).items():
            try:
                item_id = int(key)
            except (TypeError, ValueError):
                item_id = key
            vectors[item_id] = vector
        postings = {}
        norms = {}
        for item_id, vector in vectors.items():
            norms[item_id] = math.sqrt(sum(v * v for v in vector.values())) or 1.0
            for feature, value in vector.items():
                postings.setdefault(feature, []).append((item_id, value))
        return cls(postings, vectors, norms, data.get("total", len(vectors)))
