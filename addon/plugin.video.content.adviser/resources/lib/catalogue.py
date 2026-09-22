"""Construccion y cacheo del indice dentro de Kodi.

**Dos fases, y el reparto sale de una medida.** En una Raspberry Pi 4 con la
biblioteca en MySQL, leer un catalogo de varios miles de peliculas cuesta unos
2 s con los campos basicos y cerca de un minuto anadiendo `cast` y `uniqueid`.
Por eso la fase basica deja el recomendador util casi al instante y la cara va
detras, en segundo plano.
"""

import json
import os
import time

import xbmc
from adviser.domain import FeatureExtractor, SimilarityIndex
from adviser.domain.phrases import PhraseBook
from adviser.domain.prefix import PERSON, TITLE, PrefixIndex
from adviser.library import (
    BASIC_MOVIE_FIELDS,
    BASIC_TVSHOW_FIELDS,
    RICH_MOVIE_FIELDS,
    LibraryReader,
)
from adviser.storage import load, save

from .bridge import data_path, log, rpc

# **Sube cuando el indice gana un artefacto nuevo.** Sin esto, un equipo que
# actualiza se queda con los ficheros de la version anterior: existen los que
# `needs_rebuild` miraba, asi que no reconstruye, y el artefacto nuevo no
# aparece nunca. Paso con `movies.phrases.json` al subir de 0.3.0 a 0.4.1, y solo
# se ve actualizando de verdad: en una instalacion limpia no hay nada que falte.
FORMAT_VERSION = 4

INDEX_FILE = "movies.index.json"
PHRASES_FILE = "movies.phrases.json"
HISTORY_FILE = "questions.json"
PREFIX_DIR = "prefix"
STATE_FILE = "movies.state.json"

# Lo que `build` deja escrito. **Todo lo de aqui se comprueba al decidir si hay
# que reconstruir**, y una prueba lo vigila: anadir un artefacto y olvidar la
# comprobacion es lo que dejo a un equipo actualizado sin libro de frases.
# `HISTORY_FILE` no esta, y es a proposito: es del usuario, no del indice.
BUILD_ARTIFACTS = (INDEX_FILE, PREFIX_DIR, PHRASES_FILE, STATE_FILE)

__all__ = ["build", "read_index", "read_prefix", "read_phrasebook", "read_questions",
           "remember_question", "needs_rebuild", "identity_map",
           "tmdb_resolver", "tmdb_of"]


def _items(rich):
    fields = list(BASIC_MOVIE_FIELDS)
    if rich:
        fields += list(RICH_MOVIE_FIELDS)
    return LibraryReader(rpc).read("movie", fields)


def build(rich=True, cast_depth=10):
    """Construye el indice y lo deja en `addon_data`. Devuelve un resumen."""
    started = time.time()
    items = _items(rich)
    read_seconds = time.time() - started

    index = SimilarityIndex.build(items, FeatureExtractor(cast_depth=cast_depth))
    payload = index.to_dict()
    payload["rich"] = rich
    payload["built_at"] = time.time()
    payload["titles"] = {str(i["id"]): i.get("title") for i in items if i.get("id") is not None}
    payload["identity"] = _identity_payload(items)
    save(data_path(INDEX_FILE), payload)

    prefix = PrefixIndex.build(_search_terms(items))
    _save_prefix(prefix)
    # Las series se leen tambien, **solo con los campos baratos**, y unicamente
    # para poder ofrecer frases con su vocabulario: sus generos no son los de las
    # peliculas, y preguntar por una serie con el menu de las otras no ayuda.
    shows = LibraryReader(rpc).read("tvshow", list(BASIC_TVSHOW_FIELDS))
    save(data_path(PHRASES_FILE), {"movie": _phrase_material(items),
                                   "tvshow": _phrase_material(shows)})

    summary = {"items": len(items), "indexed": index.size, "rich": rich,
               "format": FORMAT_VERSION, "search_terms": prefix.size,
               "read_seconds": round(read_seconds, 2),
               "total_seconds": round(time.time() - started, 2)}
    save(data_path(STATE_FILE), summary)
    log("indice construido: %s" % json.dumps(summary))
    return summary


def _search_terms(items):
    """Lo que se puede teclear para encontrar algo: titulos y personas.

    Sale de los mismos datos que ya se han leido, asi que **no cuesta ni una
    consulta mas**. Con la fase basica hay titulos y directores; el reparto llega
    con la fase enriquecida, y hasta entonces el buscador sirve igual con menos.
    """
    terms = []
    for item in items:
        if item.get("title"):
            terms.append((item["title"], TITLE))
        for name in (item.get("director") or []):
            terms.append((name, PERSON))
        for member in (item.get("cast") or []):
            name = member.get("name") if isinstance(member, dict) else member
            if name:
                terms.append((name, PERSON))
    return terms


def _bucket_file(key):
    """Un fichero por cubo. El nombre va en hexadecimal porque la clave es una
    letra cualquiera del catalogo y no toda letra vale como nombre de fichero."""
    return os.path.join(data_path(PREFIX_DIR), "%s.json" % key.encode("utf-8").hex())


def _save_prefix(prefix):
    """Se guarda **un fichero por cubo, no uno entero**.

    El indice completo de un catalogo real pesa unos 10 MB. Cargarlo en cada
    pulsacion de tecla seria inviable en una Raspberry: el predictivo tiene que
    responder mientras el usuario teclea, no despues. Cada cubo ronda las decenas
    o centenas de kilobytes, y una consulta solo abre el suyo.
    """
    destino = data_path(PREFIX_DIR)
    if os.path.isdir(destino):
        for viejo in os.listdir(destino):
            os.remove(os.path.join(destino, viejo))
    else:
        os.makedirs(destino, exist_ok=True)
    payload = prefix.to_dict()
    for key, rows in (payload.get("buckets") or {}).items():
        save(_bucket_file(key), {"version": payload.get("version", 1),
                                 "buckets": {key: rows}})
    return len(payload.get("buckets") or {})


# Cuantas personas se ofrecen. Solo las que aparecen en varias obras: alguien con
# una sola pelicula no es una forma util de pedir algo.
PEOPLE_IN_PHRASES = 12
MIN_FILMS_PER_PERSON = 3


def _phrase_material(items):
    """Lo que este catalogo concreto puede ofrecer al componer una pregunta.

    Sale de los mismos datos ya leidos, sin una consulta de mas.
    """
    genres = {}
    decades = {}
    people = {}
    for item in items:
        for genre in (item.get("genre") or []):
            genres[genre] = genres.get(genre, 0) + 1
        year = item.get("year")
        if isinstance(year, int) and year > 1870:
            decada = year // 10 * 10
            decades[decada] = decades.get(decada, 0) + 1
        for name in (item.get("director") or []):
            people[name] = people.get(name, 0) + 1
    frecuentes = [n for n, c in sorted(people.items(), key=lambda kv: (-kv[1], kv[0]))
                  if c >= MIN_FILMS_PER_PERSON][:PEOPLE_IN_PHRASES]
    # Por presencia, no por fecha: lo primero que se ofrece debe ser lo que mas
    # probabilidades tiene de dar resultados.
    por_presencia = [d for d, _ in sorted(decades.items(), key=lambda kv: (-kv[1], -kv[0]))]
    generos = [g for g, _ in sorted(genres.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"genres": generos, "decades": por_presencia, "people": frecuentes}


def read_phrasebook(media_type="movie"):
    """El libro de frases de este catalogo para esa clase de obra."""
    try:
        material = (load(data_path(PHRASES_FILE)) or {}).get(media_type) or {}
    except (OSError, ValueError):
        return None
    if not material:
        return None
    return PhraseBook.build(genres=material.get("genres") or [],
                            people=material.get("people") or [],
                            decades=material.get("decades") or [],
                            media_type=media_type)


def read_questions(limit=20):
    """Las preguntas anteriores, de mas a menos reciente."""
    try:
        return (load(data_path(HISTORY_FILE)) or [])[:limit]
    except (OSError, ValueError):
        return []


def remember_question(question, limit=20):
    """Guarda la pregunta. Sin repetidas y con la ultima delante."""
    question = " ".join(str(question or "").split())
    if not question:
        return
    previas = [q for q in read_questions(limit=limit) if q != question]
    save(data_path(HISTORY_FILE), ([question] + previas)[:limit])


def read_prefix(query):
    """Solo el cubo que hace falta para esta consulta.

    `PrefixIndex.suggest` unicamente mira el cubo de la primera letra, asi que un
    indice con un solo cubo responde igual que el completo, y cuesta mil veces
    menos abrirlo.
    """
    from adviser.domain.prefix import MIN_QUERY, bucket_key, normalise
    needle = normalise(query)
    if len(needle) < MIN_QUERY:
        return None
    try:
        return PrefixIndex.from_dict(load(_bucket_file(bucket_key(needle))))
    except (OSError, ValueError):
        return None


def _identity_payload(items):
    """Identidad real de cada obra, para que un duplicado no cuente dos veces.

    Se prefiere el identificador externo; cuando no lo hay, titulo y ano
    normalizados. Asi funciona **tambien con la fase basica**, sin obligar a pagar
    la cara solo para deduplicar.
    """
    identity = {}
    for item in items:
        key = str(item.get("id"))
        unique = (item.get("uniqueid") or {}).get("tmdb")
        if unique:
            identity[key] = "tmdb:%s" % unique
            continue
        title = item.get("title")
        if title:
            identity[key] = "title:%s:%s" % (" ".join(str(title).split()).lower(),
                                             item.get("year"))
    return identity


def read_index():
    """Devuelve `(indice, titulos, identidad)` o `(None, {}, {})` si no hay."""
    try:
        payload = load(data_path(INDEX_FILE))
    except (OSError, ValueError):
        return None, {}, {}
    identity = payload.get("identity") or {}
    return SimilarityIndex.from_dict(payload), payload.get("titles") or {}, identity


def identity_map(identity):
    """Adapta el mapa guardado a lo que espera el nucleo."""
    def key_of(item_id):
        return identity.get(str(item_id))
    return key_of


def tmdb_of(identity, item_id):
    """Identificador de TMDB de una obra del catalogo, si se conoce."""
    value = identity.get(str(item_id)) or ""
    return value[5:] if value.startswith("tmdb:") else None


def tmdb_resolver(identity):
    """Devuelve `id_tmdb -> dbid`, que es lo que necesita la mezcla para saber
    cual de las recomendaciones externas resulta que ya la tienes."""
    inverso = {}
    for item_id, value in identity.items():
        if value.startswith("tmdb:"):
            inverso.setdefault(value[5:], int(item_id))

    def resolve(reference):
        return inverso.get(str(reference))
    return resolve


def needs_rebuild(rich):
    """Hay que reconstruir si falta algo, si es de otra fase, o si es de un
    formato anterior."""
    for artefacto in BUILD_ARTIFACTS:
        if not os.path.exists(data_path(artefacto)):
            return True
    try:
        payload = load(data_path(INDEX_FILE))
    except (OSError, ValueError):
        log("el indice guardado no se puede leer; se reconstruye", xbmc.LOGWARNING)
        return True
    if bool(payload.get("rich")) != bool(rich):
        return True
    try:
        formato = int((load(data_path(STATE_FILE)) or {}).get("format", 1))
    except (OSError, ValueError, TypeError):
        formato = 1
    if formato != FORMAT_VERSION:
        log("el indice es del formato %s y ahora es el %s; se reconstruye"
            % (formato, FORMAT_VERSION))
        return True
    return False
