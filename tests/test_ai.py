"""La capa de IA: el modelo traduce, el catalogo decide.

Ninguna prueba necesita red ni servidor: construir la peticion y leer la
respuesta son funciones puras a proposito, y esa separacion es justo lo que
permite probar los dos dialectos.
"""

import pytest
from adviser.ai import ANTHROPIC, OPENAI_COMPATIBLE, build_request, parse_response
from adviser.ai.providers import ProviderError
from adviser.ai.query import Query, QueryError, build_prompt, parse_query

GENEROS = ["Comedia", "Drama", "Ciencia ficción"]


def _peticion(provider, **kwargs):
    base = {"base_url": "http://ejemplo:11434/v1", "model": "m",
            "system": "s", "user": "u"}
    base.update(kwargs)
    return build_request(provider, **base)


def test_el_dialecto_compatible_no_exige_clave():
    """Ollama y un servidor propio no la piden; inventarse una de relleno seria peor."""
    url, headers, _ = _peticion(OPENAI_COMPATIBLE)
    assert url.endswith("/chat/completions")
    assert "Authorization" not in headers


def test_con_clave_se_manda_como_portador():
    _, headers, _ = _peticion(OPENAI_COMPATIBLE, api_key="k")
    assert headers["Authorization"] == "Bearer k"


def test_el_otro_dialecto_si_exige_clave():
    with pytest.raises(ProviderError):
        _peticion(ANTHROPIC)


def test_cada_dialecto_arma_su_cuerpo():
    _, _, compatible = _peticion(OPENAI_COMPATIBLE)
    _, _, otro = _peticion(ANTHROPIC, api_key="k")
    assert compatible["messages"][0]["role"] == "system"
    assert otro["system"] == "s"
    assert len(otro["messages"]) == 1


def test_la_barra_final_de_la_url_da_igual():
    con, _, _ = _peticion(OPENAI_COMPATIBLE, base_url="http://x/v1/")
    sin, _, _ = _peticion(OPENAI_COMPATIBLE, base_url="http://x/v1")
    assert con == sin


def test_sin_url_o_sin_modelo_falla_antes_de_salir_a_la_red():
    for hueco in ({"base_url": ""}, {"model": ""}):
        with pytest.raises(ProviderError):
            _peticion(OPENAI_COMPATIBLE, **hueco)


def test_un_proveedor_desconocido_no_pasa_en_silencio():
    with pytest.raises(ProviderError):
        _peticion("telepatia")


def test_se_lee_la_respuesta_de_cada_dialecto():
    assert parse_response(OPENAI_COMPATIBLE,
                          {"choices": [{"message": {"content": " hola "}}]}) == "hola"
    assert parse_response(ANTHROPIC, {"content": [{"text": "hola"}]}) == "hola"


def test_un_error_del_servicio_se_propaga():
    with pytest.raises(ProviderError):
        parse_response(OPENAI_COMPATIBLE, {"error": {"message": "sin cuota"}})


def test_una_respuesta_vacia_no_se_confunde_con_una_buena():
    for vacia in ({"choices": []}, {}, "esto no es un objeto"):
        with pytest.raises(ProviderError):
            parse_response(OPENAI_COMPATIBLE, vacia)


def test_el_prompt_lleva_el_vocabulario_real_del_catalogo():
    """Elegir de un menu cerrado es mas fiable que acertar el vocabulario."""
    prompt = build_prompt("algo de risa", GENEROS)
    for genero in GENEROS:
        assert genero in prompt
    assert "algo de risa" in prompt


def test_un_genero_que_el_catalogo_no_tiene_se_descarta():
    """Es un invento del modelo: no filtraria nada y llegaria a la pantalla."""
    consulta = parse_query('{"genres": ["Comedia", "Casposo"]}', GENEROS)
    assert consulta.genres == ["Comedia"]


def test_el_genero_se_devuelve_con_la_grafia_del_catalogo():
    consulta = parse_query('{"genres": ["ciencia ficción"]}', GENEROS)
    assert consulta.genres == ["Ciencia ficción"]


def test_se_tolera_que_el_modelo_envuelva_el_json():
    texto = 'Claro:\n```json\n{"max_runtime": 90}\n```\nEspero que te sirva.'
    assert parse_query(texto, GENEROS).max_runtime == 90


def test_una_respuesta_sin_json_falla_con_un_error_propio():
    for mala in ("", "no tengo ni idea", "[1,2,3]"):
        with pytest.raises(QueryError):
            parse_query(mala, GENEROS)


def test_los_numeros_absurdos_se_descartan():
    consulta = parse_query('{"year_from": 12, "year_to": 99999, "max_runtime": -5}',
                           GENEROS)
    assert (consulta.year_from, consulta.year_to, consulta.max_runtime) == (None, None, None)


def test_un_orden_inventado_se_ignora():
    assert parse_query('{"sort": "por peso"}', GENEROS).sort is None
    assert parse_query('{"sort": "rating"}', GENEROS).sort == "rating"


def test_una_consulta_sin_nada_util_se_reconoce():
    """Si el modelo no saca nada aplicable, hay que decirlo y no listar el catalogo."""
    assert parse_query('{"sort": "random"}', GENEROS).is_empty
    assert not parse_query('{"genres": ["Drama"]}', GENEROS).is_empty


def test_un_genero_suelto_vale_igual_que_una_lista():
    assert parse_query('{"genres": "Drama"}', GENEROS).genres == ["Drama"]


def test_dos_consultas_iguales_son_iguales():
    assert Query(genres=["Drama"]) == Query(genres=["Drama"])
    assert Query(genres=["Drama"]) != Query(genres=["Comedia"])


# --- de la consulta al filtro de Kodi ---------------------------------------
from adviser.ai import to_library_filter, to_sort  # noqa: E402


def test_sin_nada_que_filtrar_no_se_manda_filtro():
    """Un filtro vacio listaria el catalogo entero como si fuera una respuesta."""
    assert to_library_filter(Query()) is None


def test_una_sola_regla_no_se_envuelve():
    assert to_library_filter(Query(genres=["Drama"]))["field"] == "genre"


def test_varias_reglas_se_combinan_con_and():
    filtro = to_library_filter(Query(genres=["Drama"], max_runtime=90))
    assert len(filtro["and"]) == 2


def test_desde_un_ano_incluye_ese_ano():
    """`greaterthan` es estricto: sin restar uno se pierde el ano que se pidio."""
    filtro = to_library_filter(Query(year_from=1990))
    assert filtro["operator"] == "greaterthan"
    assert filtro["value"] == "1989"


def test_hasta_un_ano_incluye_ese_ano():
    assert to_library_filter(Query(year_to=1999))["value"] == "2000"


def test_un_intervalo_de_anos_usa_between():
    filtro = to_library_filter(Query(year_from=1990, year_to=1999))
    assert filtro["operator"] == "between"
    assert filtro["value"] == ["1990", "1999"]


def test_la_duracion_maxima_va_en_segundos_y_incluye_ese_minuto():
    """`time` esta en segundos aunque la interfaz de listas inteligentes de Kodi lo
    pida en minutos. Sin convertir, «menos de 106 minutos» pide «menos de 106
    segundos» y no contesta casi nada."""
    filtro = to_library_filter(Query(max_runtime=90))
    assert filtro["field"] == "time"
    assert filtro["value"] == str(91 * 60)


def test_una_persona_vale_como_director_o_como_interprete():
    """Quien pregunta por «algo de Spielberg» rara vez distingue los dos papeles."""
    filtro = to_library_filter(Query(people=["Spielberg"]))
    campos = {r["field"] for r in filtro["or"]}
    assert campos == {"actor", "director"}


def test_los_generos_excluidos_usan_la_negacion():
    filtro = to_library_filter(Query(exclude_genres=["Terror"]))
    assert filtro["operator"] == "isnot"


def test_el_orden_se_traduce_o_se_deja_en_manos_de_kodi():
    assert to_sort(Query(sort="rating"))["method"] == "rating"
    assert to_sort(Query()) is None
    assert to_sort(Query(sort="inventado")) is None


# --- IA_NEST, que habla su propio dialecto -----------------------------------
from adviser.ai import IA_NEST  # noqa: E402


def test_ia_nest_manda_un_solo_prompt():
    """`prompt.run` no recibe una conversacion con papeles: recibe un prompt. La
    parte de sistema no se tira, que es la que fija el formato de la respuesta."""
    url, _, body = _peticion(IA_NEST, base_url="http://ia-nest:8000")
    assert url.endswith("/prompt/run")
    assert "s" in body["prompt"] and "u" in body["prompt"]
    assert "messages" not in body


def test_ia_nest_no_exige_modelo():
    """Lo elige su router por dominio, que es su razon de ser."""
    _, _, body = _peticion(IA_NEST, base_url="http://ia-nest:8000", model="")
    assert "model" not in body


def test_ia_nest_acepta_un_modelo_si_se_fija():
    _, _, body = _peticion(IA_NEST, base_url="http://ia-nest:8000", model="uno")
    assert body["model"] == "uno"


def test_se_lee_la_respuesta_de_ia_nest():
    assert parse_response(IA_NEST, {"response": " hola ", "model": "x"}) == "hola"


def test_una_respuesta_vacia_de_ia_nest_no_pasa_por_buena():
    with pytest.raises(ProviderError):
        parse_response(IA_NEST, {"response": "", "model": "x"})


def test_los_tres_proveedores_dan_url_cabeceras_y_cuerpo():
    """Contrato comun: anadir un cuarto no deberia tocar nada fuera de providers."""
    from adviser.ai.providers import PROVIDERS
    for proveedor in PROVIDERS:
        url, headers, body = _peticion(proveedor, api_key="k")
        assert url.startswith("http")
        assert headers["Content-Type"] == "application/json"
        assert isinstance(body, dict)


def test_ia_nest_lleva_la_identidad_como_objeto():
    """Comprobado contra el servicio real: una cadena da «identity debe ser un
    objeto». Lleva quien pregunta, desde donde, y una sesion."""
    identidad = {"user_id": "kodi.gg", "service": "kodi.adviser", "session_id": "s1"}
    _, _, body = _peticion(IA_NEST, base_url="http://x:8001", identity=identidad)
    assert body["identity"] == identidad


def test_sin_identidad_no_se_manda_el_campo():
    """Un servicio que no la pide no tiene por que recibir un objeto vacio."""
    _, _, body = _peticion(IA_NEST, base_url="http://x:8001")
    assert "identity" not in body


def test_los_otros_dialectos_ignoran_la_identidad():
    """Es una particularidad de ese servicio, no del contrato comun."""
    for proveedor in (OPENAI_COMPATIBLE, ANTHROPIC):
        _, _, body = _peticion(proveedor, api_key="k", identity={"user_id": "x"})
        assert "identity" not in body


# --- el prompt dice que clase de obra se busca --------------------------------
from adviser.ai.query import MEDIA_NAMES  # noqa: E402


def test_el_prompt_dice_si_se_busca_pelicula_o_serie():
    """Sin decirlo, «algo de humor» pedido desde las series se traduce igual que
    desde las peliculas: el filtro acierta por casualidad, no por entenderlo."""
    pelicula = build_prompt("algo de humor", GENEROS, "movie")
    serie = build_prompt("algo de humor", GENEROS, "tvshow")
    assert MEDIA_NAMES["movie"] in pelicula
    assert MEDIA_NAMES["tvshow"] in serie
    assert pelicula != serie


def test_por_defecto_se_busca_una_pelicula():
    assert MEDIA_NAMES["movie"] in build_prompt("algo", GENEROS)


def test_el_sistema_avisa_de_que_se_le_dice_la_clase():
    from adviser.ai.query import SYSTEM_PROMPT
    assert "clase de obra" in SYSTEM_PROMPT


def test_y_y_o_no_son_lo_mismo():
    """Una regla de genero con varios valores casa con cualquiera de ellos, asi
    que «terror y suspense» daba el mismo resultado que «terror o suspense», que
    en un catalogo grande es una diferencia de un orden de magnitud."""
    cualquiera = to_library_filter(Query(genres=["Comedia", "Drama"]))
    todos = to_library_filter(Query(genres_all=["Comedia", "Drama"]))
    assert cualquiera != todos
    assert cualquiera["operator"] == "is" and len(cualquiera["value"]) == 2
    assert len(todos["and"]) == 2
    assert all(r["value"] in ("Comedia", "Drama") for r in todos["and"])


def test_el_modelo_puede_pedir_las_dos_cosas_a_la_vez():
    consulta = parse_query('{"genres": ["Comedia"], "genres_all": ["Drama"]}', GENEROS)
    assert consulta.genres == ["Comedia"] and consulta.genres_all == ["Drama"]
    assert len(to_library_filter(consulta)["and"]) == 2


def test_un_genero_inventado_tampoco_cuela_por_la_via_del_y():
    assert parse_query('{"genres_all": ["Casposo"]}', GENEROS).genres_all == []


def test_una_consulta_con_solo_genres_all_no_esta_vacia():
    assert not parse_query('{"genres_all": ["Drama"]}', GENEROS).is_empty
