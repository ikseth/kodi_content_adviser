"""El lector tiene que devolver el catalogo entero pase lo que pase con la paginacion.

La propiedad que importa no es «hace N llamadas» sino «no se deja ni pierde nada»:
un test que fijara el numero de llamadas se rompera con cualquier mejora del
tamano de pagina, que es justo un cambio bueno.
"""

import pytest
from adviser.library import BASIC_MOVIE_FIELDS, LibraryReader
from fakes import FakeTransport, movie


def _transporte(cuantas):
    return FakeTransport({"VideoLibrary.GetMovies": [movie(i) for i in range(cuantas)]})


@pytest.mark.parametrize("cuantas", [0, 1, 7, 500, 501, 1000])
@pytest.mark.parametrize("pagina", [1, 3, 500])
def test_lee_el_catalogo_entero_sea_cual_sea_la_pagina(cuantas, pagina):
    lector = LibraryReader(_transporte(cuantas), page_size=pagina)
    items = lector.read("movie", BASIC_MOVIE_FIELDS)
    assert len(items) == cuantas
    assert [i["movieid"] for i in items] == list(range(cuantas))


def test_el_tamano_de_pagina_no_cambia_el_resultado():
    referencia = LibraryReader(_transporte(123), page_size=500).read("movie", BASIC_MOVIE_FIELDS)
    for pagina in (1, 2, 50, 122, 123, 124):
        otro = LibraryReader(_transporte(123), page_size=pagina).read("movie", BASIC_MOVIE_FIELDS)
        assert otro == referencia


def test_normaliza_el_identificador_y_el_tipo():
    items = LibraryReader(_transporte(3)).read("movie", BASIC_MOVIE_FIELDS)
    assert all(i["id"] == i["movieid"] for i in items)
    assert all(i["media_type"] == "movie" for i in items)


def test_pide_exactamente_los_campos_que_se_le_dan():
    transporte = _transporte(2)
    LibraryReader(transporte).read("movie", BASIC_MOVIE_FIELDS)
    _, params = transporte.calls[0]
    assert params["properties"] == list(BASIC_MOVIE_FIELDS)


def test_rechaza_un_tipo_de_medio_desconocido():
    with pytest.raises(ValueError):
        LibraryReader(_transporte(1)).read("libro", BASIC_MOVIE_FIELDS)


def test_rechaza_una_pagina_no_positiva():
    with pytest.raises(ValueError):
        LibraryReader(_transporte(1), page_size=0)
