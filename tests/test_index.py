"""Propiedades del indice de similitud.

Ninguna prueba fija una puntuacion concreta: fijan **relaciones** entre
puntuaciones. Una constante se rompe con los cambios buenos igual que con los
malos, y aqui va a haber cambios de pesos.
"""

from adviser.domain import FeatureExtractor, SimilarityIndex
from fakes import movie


def _indice(items, **kwargs):
    for item in items:
        item.setdefault("id", item["movieid"])
    return SimilarityIndex.build(items, FeatureExtractor(), **kwargs)


def test_un_item_nunca_es_vecino_de_si_mismo():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(20)]
    indice = _indice(items)
    for item in items:
        assert all(otro != item["movieid"] for otro, _ in indice.neighbours(item["movieid"]))


def test_la_puntuacion_esta_acotada_entre_cero_y_uno():
    items = [movie(i, genre=["Accion", "Drama"], director=["D%d" % (i % 4)],
                   studio=["E%d" % (i % 5)]) for i in range(40)]
    indice = _indice(items)
    for _, puntuacion in indice.neighbours(0, limit=None):
        assert 0.0 <= puntuacion <= 1.0 + 1e-9


def test_dos_fichas_identicas_se_parecen_mas_que_ninguna_otra_pareja():
    items = [movie(1, genre=["Accion"], director=["Mismo"]),
             movie(2, genre=["Accion"], director=["Mismo"]),
             movie(3, genre=["Accion"], director=["Otro"])]
    indice = _indice(items)
    vecinos = dict(indice.neighbours(1, limit=None))
    assert vecinos[2] > vecinos[3]


def test_sin_rasgos_compartidos_no_hay_parecido():
    items = [movie(1, genre=["Accion"]), movie(2, genre=["Documental"])]
    indice = _indice(items)
    assert indice.neighbours(1) == []


def test_compartir_un_rasgo_raro_puntua_mas_que_compartir_uno_comun():
    """Es el nucleo del modelo: el idf tiene que mandar sobre la frecuencia bruta."""
    items = [movie(i, genre=["Comun"]) for i in range(30)]
    items[1]["director"] = ["Raro"]
    items[2]["director"] = ["Raro"]
    indice = _indice(items)
    vecinos = dict(indice.neighbours(1, limit=None))
    compartiendo_raro = vecinos[2]
    solo_comun = max(v for k, v in vecinos.items() if k != 2)
    assert compartiendo_raro > solo_comun


def test_un_rasgo_omnipresente_se_descarta_por_coste():
    """Si todo el catalogo comparte un rasgo, recorrer su lista no aporta nada."""
    items = [movie(i, genre=["Todos"]) for i in range(200)]
    indice = _indice(items, max_document_ratio=0.5)
    assert indice.size == 0


def test_en_un_catalogo_pequeno_no_se_descarta_nada():
    """La guarda es sobre la longitud de la lista, no sobre la proporcion: con
    pocas obras, descartar por porcentaje borraria justo el parecido buscado."""
    items = [movie(i, genre=["Todos"]) for i in range(5)]
    assert _indice(items).size == 5


def test_el_limite_recorta_pero_no_reordena():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)],
                   studio=["E%d" % (i % 7)]) for i in range(30)]
    indice = _indice(items)
    completo = indice.neighbours(0, limit=None)
    assert indice.neighbours(0, limit=5) == completo[:5]


def test_se_pueden_excluir_candidatos():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(10)]
    indice = _indice(items)
    excluidos = {2, 3, 4}
    assert not excluidos & {o for o, _ in indice.neighbours(0, limit=None, exclude=excluidos)}


def test_el_indice_sobrevive_a_un_viaje_de_ida_y_vuelta():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)],
                   studio=["E%d" % (i % 5)]) for i in range(25)]
    original = _indice(items)
    copia = SimilarityIndex.from_dict(original.to_dict())
    assert copia.size == original.size
    for item in items:
        assert copia.neighbours(item["movieid"]) == original.neighbours(item["movieid"])


def test_un_item_sin_identificador_se_ignora():
    items = [{"genre": ["Accion"]}, movie(1, genre=["Accion"])]
    assert SimilarityIndex.build(items, FeatureExtractor()).size <= 1


def test_un_catalogo_vacio_da_un_indice_vacio():
    indice = SimilarityIndex.build([], FeatureExtractor())
    assert indice.size == 0
    assert indice.neighbours(1) == []


def test_el_umbral_recorta_por_abajo_y_no_reordena():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 4)],
                   studio=["E%d" % (i % 6)]) for i in range(40)]
    indice = _indice(items)
    completo = indice.neighbours(0, limit=None)
    umbral = completo[len(completo) // 2][1]
    filtrado = indice.neighbours(0, limit=None, min_score=umbral)
    assert all(p >= umbral for _, p in filtrado)
    assert filtrado == [par for par in completo if par[1] >= umbral]


def test_un_umbral_imposible_deja_la_lista_vacia():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(10)]
    assert _indice(items).neighbours(0, min_score=1.1) == []
