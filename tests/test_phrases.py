"""Componer la pregunta a golpe de mando.

El caso de uso manda: con un mando, cada pulsacion cuesta. Una sugerencia que no
lleve a ninguna pelicula de la casa es peor que ninguna, porque ademas se ha
pagado el recorrido hasta ella.
"""

from adviser.domain.phrases import DURATION, GENRE, PhraseBook

GENEROS = ["Comedia", "Terror", "Drama"]
PERSONAS = ["Steven Spielberg"]
DECADAS = [1980, 1990]


def _libro(**kwargs):
    base = {"genres": GENEROS, "people": PERSONAS, "decades": DECADAS}
    base.update(kwargs)
    return PhraseBook.build(**base)


def _frases(resultados):
    return [frase for frase, _ in resultados]


def test_con_la_caja_vacia_se_ofrece_por_donde_empezar():
    assert _frases(_libro().suggest(""))[0]


def test_solo_se_ofrecen_generos_que_existen_en_el_catalogo():
    """Ofrecer «del oeste» sin tener westerns es pagar el recorrido para nada."""
    libro = _libro(genres=["Comedia"])
    frases = " ".join(_frases(libro.suggest("algo", limit=0)))
    assert "de risa" in frases
    assert "del oeste" not in frases


def test_un_catalogo_sin_generos_no_ofrece_ninguno():
    libro = PhraseBook.build(genres=[], people=[], decades=[])
    assert not [f for f in libro._fragments if f.slot == GENRE]


def test_solo_se_ofrecen_decadas_que_existen():
    frases = " ".join(_frases(_libro(decades=[1980]).suggest("algo de risa", limit=0)))
    assert "ochenta" in frases
    assert "noventa" not in frases


def test_no_se_ofrece_dos_veces_la_misma_clase_de_cosa():
    """Con el genero ya puesto, seguir ofreciendo generos no acota nada."""
    libro = _libro()
    frases = " ".join(_frases(libro.suggest("algo de risa", limit=0)))
    assert "de miedo" not in frases


def test_mientras_se_escribe_se_completa_y_no_se_anade():
    """«algo de r» va a medias de «de risa». Anadir daria «algo de r de miedo»."""
    frases = _frases(_libro().suggest("algo de r", limit=0))
    assert frases == ["algo de risa"]


def test_cuando_nada_encaja_se_ofrece_continuacion():
    """«algo» no empieza ningun fragmento, asi que toca seguir, no completar."""
    frases = _frases(_libro().suggest("algo", limit=0))
    assert frases
    assert all(f.startswith("algo ") for f in frases)


def test_lo_ya_preguntado_va_primero():
    """A partir del tercer uso es lo que mas se repite, y no cuesta nada."""
    previa = "algo de risa que dure poco"
    assert _frases(_libro().suggest("algo", history=[previa]))[0] == previa


def test_el_historial_se_filtra_por_lo_escrito():
    libro = _libro()
    assert "algo de miedo" not in _frases(libro.suggest("una peli", history=["algo de miedo"]))


def test_da_igual_la_tilde_y_la_mayuscula():
    libro = _libro(genres=["Ciencia ficción"])
    assert _frases(libro.suggest("ALGO DE CIENCIA F", limit=0))


def test_no_se_ofrece_lo_que_ya_esta_escrito_entero():
    assert "algo de risa" not in _frases(_libro().suggest("algo de risa", limit=0))


def test_se_respeta_el_limite():
    assert len(_libro().suggest("algo", limit=3)) == 3


def test_sin_limite_salen_todas():
    assert len(_libro().suggest("algo", limit=0)) > 3


def test_la_frase_ofrecida_es_la_que_quedara_escrita():
    """Se enseña el resultado, no el trozo: ver lo que vas a obtener evita que el
    texto cambie de una forma que no esperabas."""
    for frase, etiqueta in _libro().suggest("algo", limit=5):
        assert frase.startswith("algo")
        assert etiqueta in frase


def test_la_duracion_se_ofrece_sin_concordancia_de_genero():
    """«algo corta» no es castellano; tiene que encajar tras cualquier arranque."""
    libro = _libro()
    for arranque in ("algo", "una peli"):
        for frase, _ in libro.suggest("%s de risa" % arranque, limit=0):
            assert " corta" not in frase
    assert any(f.slot == DURATION for f in libro._fragments)


def test_las_decadas_del_siglo_veinte_no_se_confunden_con_las_de_ahora():
    """`1920` no es «dos mil veinte». Mirar solo las dos ultimas cifras ofrecia
    «de los dos mil veinte» para peliculas de 1920: una forma segura de no
    encontrar nada."""
    frases = " ".join(_frases(_libro(decades=[1920]).suggest("algo de risa", limit=0)))
    assert "de los veinte" in frases
    assert "dos mil" not in frases
    otras = " ".join(_frases(_libro(decades=[2020]).suggest("algo de risa", limit=0)))
    assert "de los dos mil veinte" in otras


def test_las_decadas_se_ofrecen_en_el_orden_recibido():
    """Quien construye el material las ordena por cuantas peliculas hay. Por
    fecha, lo primero serian los anos veinte, que suelen ser cuatro peliculas."""
    libro = _libro(decades=[1990, 1920])
    frases = _frases(libro.suggest("algo de risa", limit=0))
    eras = [f for f in frases if "de los " in f]
    assert eras.index("algo de risa de los noventa") < eras.index("algo de risa de los veinte")


def test_a_una_serie_no_se_le_pregunta_por_la_duracion():
    """No es un dato de la serie sino de cada episodio: preguntarlo no lleva a
    ningun sitio."""
    libro = _libro(media_type="tvshow")
    frases = " ".join(_frases(libro.suggest("algo de risa", limit=0)))
    assert "dure" not in frases
    assert "dure" in " ".join(_frases(_libro().suggest("algo de risa", limit=0)))


# --- encadenar generos --------------------------------------------------------
def test_tras_elegir_un_genero_se_ofrece_encadenar():
    """«algo de terror y suspense» y «algo de aventuras o familiar» son peticiones
    normales, y sin conectores no habia forma de componerlas."""
    frases = _frases(_libro().suggest("algo de risa", limit=0))
    assert any(f.endswith(" y") for f in frases)
    assert any(f.endswith(" o") for f in frases)


def test_tras_un_conector_vuelven_los_generos():
    """Es lo que se estaba pidiendo al pulsarlo."""
    frases = _frases(_libro().suggest("algo de risa y", limit=0))
    assert frases
    assert all(f.startswith("algo de risa y ") for f in frases)


def test_no_se_repite_el_genero_que_ya_esta():
    frases = _frases(_libro().suggest("algo de risa y", limit=0))
    assert not any(f.endswith("y de risa") for f in frases)


def test_sin_genero_no_se_ofrece_encadenar():
    """Un conector sin nada que encadenar no lleva a ningun sitio."""
    frases = _frases(_libro().suggest("algo", limit=0))
    assert not any(f.endswith(" y") or f.endswith(" o") for f in frases)


def test_se_puede_encadenar_mas_de_una_vez():
    frases = _frases(_libro().suggest("algo de risa y de miedo", limit=0))
    assert any(f.endswith(" y") for f in frases)


def test_el_genero_se_reconoce_aunque_se_escriba_con_su_nombre_real():
    """Ofrecemos «de miedo» pero alguien puede teclear «de terror». Sin esto se le
    seguian ofreciendo mas generos: «algo de terror de risa»."""
    frases = _frases(_libro().suggest("algo de terror", limit=0))
    assert not any("de risa" in f for f in frases if " y " not in f and " o " not in f)
    assert any(f.endswith(" y") for f in frases)


def test_ya_no_se_ofrece_decir_si_es_pelicula_o_serie():
    """El sistema ya lo sabe por donde se ha pulsado: hacerselo teclear es cobrar
    una pulsacion por una informacion que ya se tiene."""
    for tipo in ("movie", "tvshow"):
        arranques = _frases(_libro(media_type=tipo).suggest("", limit=0))
        assert not any("serie" in a or "peli" in a for a in arranques)
