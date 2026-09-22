"""Propiedades de la mezcla entre motor local y fuente externa."""

from adviser.domain import combine
from adviser.domain.blend import LIBRARY, OUTSIDE


def _sin_catalogo(_):
    return None


def test_sin_nada_no_hay_nada():
    assert combine([], [], 10, _sin_catalogo) == []


def test_lo_local_va_primero():
    """Ya paso el umbral y ademas se puede reproducir."""
    fila = combine([(1, 0.9), (2, 0.5)], [("t9", "De fuera")], 10, _sin_catalogo)
    assert [c for c, _, _ in fila][:2] == [LIBRARY, LIBRARY]


def test_lo_externo_que_si_tienes_sube_a_reproducible():
    """El caso que justifica toda la mezcla: tu catalogo, relacion que el motor
    local no vio."""
    fila = combine([], [("t9", "La tienes")], 10, lambda r: 77 if r == "t9" else None)
    assert fila == [(LIBRARY, 77, None)]


def test_lo_externo_que_no_tienes_se_marca_aparte():
    fila = combine([], [("t9", "No la tienes")], 10, _sin_catalogo)
    assert fila == [(OUTSIDE, "t9", "No la tienes")]


def test_se_puede_ocultar_del_todo_lo_que_no_se_tiene():
    fila = combine([], [("t9", "No la tienes")], 10, _sin_catalogo, include_outside=False)
    assert fila == []


def test_no_se_repite_lo_que_ya_estaba_por_la_via_local():
    """La fuente externa suele proponer justo lo que el motor local ya acerto."""
    fila = combine([(5, 0.9)], [("t5", "La misma")], 10, lambda _: 5)
    assert len(fila) == 1


def test_no_se_repite_dentro_de_lo_externo():
    fila = combine([], [("a", "Una"), ("b", "Otra")], 10, lambda _: 42)
    assert len(fila) == 1


def test_se_respetan_las_exclusiones():
    """Lo ya visto, o la propia obra consultada, no vuelven a aparecer."""
    fila = combine([(1, 0.9), (2, 0.8)], [], 10, _sin_catalogo, exclude={1})
    assert [r for _, r, _ in fila] == [2]


def test_una_exclusion_tambien_vale_para_lo_que_llega_de_fuera():
    fila = combine([], [("t1", "Una")], 10, lambda _: 1, exclude={1})
    assert fila == []


def test_nunca_se_devuelven_mas_de_los_pedidos():
    local = [(i, 1.0 / (i + 1)) for i in range(20)]
    externo = [("t%d" % i, "Fuera %d" % i) for i in range(20)]
    for cuantos in (1, 3, 7, 25):
        assert len(combine(local, externo, cuantos, _sin_catalogo)) <= cuantos


def test_sin_limite_entra_todo():
    fila = combine([(1, 0.9)], [("t2", "Dos"), ("t3", "Tres")], 0, _sin_catalogo)
    assert len(fila) == 3


def test_lo_local_conserva_su_orden():
    local = [(3, 0.9), (1, 0.7), (2, 0.5)]
    fila = combine(local, [], 10, _sin_catalogo)
    assert [r for _, r, _ in fila] == [3, 1, 2]


def test_lo_de_fuera_conserva_el_orden_de_la_fuente():
    externo = [("c", "C"), ("a", "A"), ("b", "B")]
    fila = combine([], externo, 10, _sin_catalogo)
    assert [t for _, _, t in fila] == ["C", "A", "B"]
