"""Propiedades de la extraccion de rasgos."""

from adviser.domain import FeatureExtractor


def test_una_ficha_vacia_no_revienta():
    assert FeatureExtractor().extract({}) == {}


def test_una_ficha_incompleta_sigue_siendo_indexable():
    """Degradar es preferible a excluir: sin reparto y sin estudio todavia hay senal."""
    rasgos = FeatureExtractor().extract({"genre": ["Drama"], "year": 1994})
    assert rasgos


def test_los_espacios_de_nombres_no_se_mezclan():
    """Un estudio y un genero que se llamen igual no pueden ser el mismo rasgo."""
    rasgos = FeatureExtractor().extract({"genre": ["Fox"], "studio": ["Fox"]})
    assert len(rasgos) == 2


def test_no_distingue_por_mayusculas_ni_espacios_sobrantes():
    extractor = FeatureExtractor()
    uno = extractor.extract({"director": ["  John  McTiernan "]})
    otro = extractor.extract({"director": ["john mctiernan"]})
    assert uno == otro


def test_el_ano_se_agrupa_por_decada():
    extractor = FeatureExtractor()
    assert extractor.extract({"year": 1981}) == extractor.extract({"year": 1989})
    assert extractor.extract({"year": 1981}) != extractor.extract({"year": 1991})


def test_un_ano_invalido_no_genera_decada():
    assert FeatureExtractor().extract({"year": 0}) == {}


def test_el_reparto_se_corta_por_profundidad():
    reparto = [{"name": "Actor %d" % i} for i in range(50)]
    rasgos = FeatureExtractor(cast_depth=5).extract({"cast": reparto})
    assert len(rasgos) == 5


def test_la_coleccion_pesa_mas_que_el_genero():
    """No es un numero concreto: es el orden, que es lo que sostiene el modelo."""
    extractor = FeatureExtractor()
    coleccion = extractor.extract({"set": "Arma letal"})
    genero = extractor.extract({"genre": ["Accion"]})
    assert max(coleccion.values()) > max(genero.values())


def test_los_pesos_se_pueden_ajustar():
    extractor = FeatureExtractor(weights={"genre": 99.0})
    assert max(extractor.extract({"genre": ["Accion"]}).values()) == 99.0


def test_un_genero_suelto_en_texto_vale_igual_que_una_lista():
    extractor = FeatureExtractor()
    assert extractor.extract({"genre": "Drama"}) == extractor.extract({"genre": ["Drama"]})
