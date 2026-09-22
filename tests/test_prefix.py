"""Propiedades del buscador predictivo.

El caso de uso manda sobre todo lo demas: **esto se teclea con un mando**, letra a
letra sobre una cuadricula. Cada pulsacion de mas es un coste real.
"""

from adviser.domain.prefix import PERSON, TITLE, PrefixIndex, normalise

CATALOGO = [
    ("La jungla de cristal", TITLE),
    ("Jungla de cristal 2: Alerta roja", TITLE),
    ("El señor de los anillos", TITLE),
    ("Amélie", TITLE),
    ("Bruce Willis", PERSON),
    ("Alan Rickman", PERSON),
]


def _indice(terms=None):
    return PrefixIndex.build(terms if terms is not None else CATALOGO)


def _textos(resultados):
    return [texto for texto, _ in resultados]


def test_una_consulta_vacia_no_sugiere_nada():
    for vacia in ("", "   ", None):
        assert _indice().suggest(vacia) == []


def test_con_una_sola_letra_no_se_sugiere():
    """Nueve sugerencias sacadas de una inicial no ayudan en un catalogo de miles,
    y mantener cubos de una letra cuesta megas en cada pulsacion."""
    assert _indice().suggest("j") == []
    assert _indice().suggest("ju")


def test_encuentra_por_una_palabra_del_medio():
    """Nadie teclea «La jungla de cristal» desde la «L»."""
    assert "La jungla de cristal" in _textos(_indice().suggest("jungla"))


def test_da_igual_la_tilde():
    assert _textos(_indice().suggest("amelie")) == _textos(_indice().suggest("amélie"))


def test_da_igual_la_ene_con_virgulilla():
    """Plegarla enseña de mas; no plegarla no enseña nada."""
    assert "El señor de los anillos" in _textos(_indice().suggest("senor"))


def test_da_igual_mayusculas_o_minusculas():
    assert _textos(_indice().suggest("JUNGLA")) == _textos(_indice().suggest("jungla"))


def test_no_se_entra_por_un_articulo():
    """Buscar «de» devolveria medio catalogo y no ayudaria a nadie."""
    assert not _textos(_indice().suggest("de cristal"))


def test_pero_si_se_entra_por_el_principio_literal():
    assert "La jungla de cristal" in _textos(_indice().suggest("la jungla"))


def test_una_pelicula_gana_a_una_persona_cuando_empatan():
    indice = PrefixIndex.build([("Alan", PERSON), ("Alan", TITLE), ("Alarma", TITLE)])
    assert indice.suggest("alan")[0][1] == TITLE


def test_gana_el_termino_que_empieza_por_la_consulta():
    """«jungla» describe mejor a «Jungla de cristal 2» que a «La jungla de cristal»."""
    assert _textos(_indice().suggest("jungla"))[0].startswith("Jungla")


def test_se_respeta_el_limite():
    indice = PrefixIndex.build([("Alarma %d" % i, TITLE) for i in range(50)])
    assert len(indice.suggest("alarma", limit=7)) == 7


def test_sin_limite_salen_todas():
    indice = PrefixIndex.build([("Alarma %d" % i, TITLE) for i in range(12)])
    assert len(indice.suggest("alarma", limit=0)) == 12


def test_un_termino_repetido_se_funde():
    indice = PrefixIndex.build([("Gladiator", TITLE), ("Gladiator", TITLE)])
    assert len(indice.suggest("glad")) == 1


def test_el_indice_sobrevive_a_un_viaje_de_ida_y_vuelta():
    original = _indice()
    copia = PrefixIndex.from_dict(original.to_dict())
    for consulta in ("jungla", "senor", "bru", "a"):
        assert copia.suggest(consulta) == original.suggest(consulta)


def test_una_ficha_sin_titulo_no_entra_ni_revienta():
    indice = PrefixIndex.build([(None, TITLE), ("", TITLE), ("  ", TITLE),
                                ("Gladiator", TITLE)])
    assert indice.size == 1


def test_normalizar_es_estable():
    """Si no lo fuera, el indice guardado y la consulta dejarian de casar."""
    for texto in ("Amélie", "EL SEÑOR", "  espacios   raros  "):
        assert normalise(texto) == normalise(normalise(texto))


def test_lo_que_se_devuelve_es_texto_y_clase_y_no_texto_y_etiqueta():
    """El segundo elemento es la CLASE, no algo que pintar.

    Confundirlas pinto la palabra «title» en la lista del teclado en vez del
    titulo de la pelicula. Aqui queda fijado para que se vea al leerlo.
    """
    for texto, clase in _indice().suggest("jungla", limit=0):
        assert clase in (TITLE, PERSON)
        assert texto not in (TITLE, PERSON)
