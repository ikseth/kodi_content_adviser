"""Propiedades de la fila «porque viste…».

La distincion entre visto y empezado no es un detalle: salio de mirar la
biblioteca real, donde hay peliculas con fecha de hoy y cuenta cero.
"""

from adviser.domain import FeatureExtractor, SimilarityIndex, recent_seeds, recommend_from_history
from fakes import movie


def _vista(movie_id, cuando, playcount=1):
    return movie(movie_id, lastplayed=cuando, playcount=playcount)


def test_lo_nunca_tocado_no_entra():
    assert recent_seeds([movie(1), movie(2, playcount=3)]) == []


def test_lo_empezado_y_no_acabado_queda_fuera_por_defecto():
    items = [_vista(1, "2026-09-20 10:00:00", playcount=0)]
    assert recent_seeds(items) == []
    assert recent_seeds(items, include_unfinished=True)


def test_lo_empezado_pesa_menos_que_lo_acabado():
    acabada = recent_seeds([_vista(1, "2026-09-20 10:00:00")], include_unfinished=True)
    empezada = recent_seeds([_vista(1, "2026-09-20 10:00:00", playcount=0)],
                            include_unfinished=True)
    assert empezada[0][1] < acabada[0][1]


def test_manda_la_fecha_y_no_el_orden_de_la_lista():
    items = [_vista(1, "2026-01-01 00:00:00"),
             _vista(2, "2026-09-20 00:00:00"),
             _vista(3, "2026-05-01 00:00:00")]
    assert [i for i, _ in recent_seeds(items)] == [2, 3, 1]


def test_lo_mas_reciente_pesa_mas():
    items = [_vista(i, "2026-09-%02d 00:00:00" % (i + 1)) for i in range(5)]
    pesos = [p for _, p in recent_seeds(items)]
    assert pesos == sorted(pesos, reverse=True)


def test_se_respeta_el_numero_de_semillas():
    items = [_vista(i, "2026-09-%02d 00:00:00" % (i + 1)) for i in range(20)]
    assert len(recent_seeds(items, limit=7)) == 7


def _indice(items):
    for item in items:
        item.setdefault("id", item["movieid"])
    return SimilarityIndex.build(items, FeatureExtractor())


def test_las_semillas_nunca_se_recomiendan_a_si_mismas():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(20)]
    indice = _indice(items)
    semillas = [(1, 1.0), (2, 0.9)]
    devueltos = {o for o, _, _ in recommend_from_history(indice, semillas, limit=None)}
    assert not devueltos & {1, 2}


def test_gustar_a_varias_semillas_sube_mas_que_gustar_mucho_a_una():
    """Es lo que separa una fila «porque viste esto» de diez filas pegadas."""
    items = [movie(1, director=["A"]), movie(2, director=["B"]), movie(3, director=["C"]),
             movie(10, director=["A", "B", "C"]),
             movie(11, director=["A"], studio=["X"])]
    items.append(movie(12, studio=["X"]))
    indice = _indice(items)
    semillas = [(1, 1.0), (2, 1.0), (3, 1.0)]
    puntuaciones = {o: p for o, p, _ in recommend_from_history(indice, semillas, limit=None)}
    assert puntuaciones[10] > puntuaciones[11]


def test_cada_recomendacion_dice_de_que_semilla_viene():
    items = [movie(1, director=["A"]), movie(2, director=["B"]),
             movie(10, director=["A"]), movie(20, director=["B"])]
    indice = _indice(items)
    razones = {o: r for o, _, r in recommend_from_history(indice, [(1, 1.0), (2, 1.0)],
                                                          limit=None)}
    assert razones[10] == 1
    assert razones[20] == 2


def test_lo_ya_visto_se_puede_excluir():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(15)]
    indice = _indice(items)
    visto = {5, 6, 7}
    devueltos = {o for o, _, _ in recommend_from_history(indice, [(1, 1.0)], limit=None,
                                                         exclude=visto)}
    assert not devueltos & visto


def test_sin_semillas_no_hay_fila():
    assert recommend_from_history(_indice([movie(1, genre=["Accion"])]), []) == []


def _catalogo_con_saga():
    """Reproduce la forma del caso real: una semilla con saga detras y otras sueltas."""
    items = [movie(1, set="Saga", genre=["Accion"]),
             movie(2, set="Saga", genre=["Accion"]),
             movie(3, set="Saga", genre=["Accion"]),
             movie(4, set="Saga", genre=["Accion"]),
             movie(100, director=["Otra"], genre=["Drama"]),
             movie(101, director=["Otra"], genre=["Drama"]),
             movie(102, director=["Otra"], genre=["Drama"])]
    return items


def test_una_semilla_con_saga_no_se_queda_con_la_fila():
    """El monocultivo medido con datos reales: sin tope, una semilla ocupaba 7 de 10."""
    indice = _indice(_catalogo_con_saga())
    semillas = [(1, 1.0), (100, 0.85)]
    fila = recommend_from_history(indice, semillas, limit=10, max_per_seed=2)
    por_semilla = {}
    for _, _, porque in fila:
        por_semilla[porque] = por_semilla.get(porque, 0) + 1
    assert max(por_semilla.values()) <= 2


def test_sin_tope_vuelve_el_monocultivo():
    """Prueba que el tope es lo que arregla el problema, y no otra cosa."""
    indice = _indice(_catalogo_con_saga())
    semillas = [(1, 1.0), (100, 0.85)]
    sin_tope = recommend_from_history(indice, semillas, limit=10, max_per_seed=0)
    por_semilla = {}
    for _, _, porque in sin_tope:
        por_semilla[porque] = por_semilla.get(porque, 0) + 1
    assert max(por_semilla.values()) > 2


def test_una_obra_catalogada_dos_veces_sale_una_sola_vez():
    items = [movie(1, director=["A"]), movie(10, director=["A"]), movie(11, director=["A"])]
    indice = _indice(items)
    claves = {10: ("misma", 1999), 11: ("misma", 1999)}
    fila = recommend_from_history(indice, [(1, 1.0)], limit=10,
                                  key_of=claves.get, min_score=0.0)
    assert len(fila) == 1


def test_una_semilla_no_se_recomienda_a_si_misma_por_su_duplicado():
    """Salio con datos reales: el resultado numero 1 era la propia semilla."""
    items = [movie(1, director=["A"]), movie(2, director=["A"])]
    indice = _indice(items)
    claves = {1: ("misma", 1977), 2: ("misma", 1977)}
    fila = recommend_from_history(indice, [(1, 1.0)], limit=10,
                                  key_of=claves.get, min_score=0.0)
    assert fila == []


def test_sin_clave_conocida_no_se_deduplica():
    """Una ficha sin identidad fiable no se descarta: degradar, no excluir."""
    items = [movie(1, director=["A"]), movie(10, director=["A"]), movie(11, director=["A"])]
    indice = _indice(items)
    fila = recommend_from_history(indice, [(1, 1.0)], limit=10,
                                  key_of=lambda _: None, min_score=0.0)
    assert len(fila) == 2


def test_el_umbral_tambien_se_aplica_a_la_fila():
    items = [movie(i, genre=["Accion"], director=["D%d" % (i % 3)]) for i in range(20)]
    indice = _indice(items)
    assert recommend_from_history(indice, [(1, 1.0)], limit=None, min_score=1.1) == []
