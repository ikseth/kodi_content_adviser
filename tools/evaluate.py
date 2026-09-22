"""Pone el motor local al lado de TMDB para que un humano los compare.

    python3 tools/evaluate.py --index indice/movies.json --sample 5
    python3 tools/evaluate.py --index indice/movies.json --history

El criterio de salida de este bloque **no es que pasen las pruebas**: es que el
propietario mire esta comparacion y diga si el motor local se sostiene solo. De esa
respuesta depende si el proyecto es un motor propio o una capa de personalizacion
sobre lo que ya existe.

TMDB se consulta a traves de `plugin.video.themoviedb.helper`, y **por
`recommendations`, nunca por `similar`**: medido, `similar` devuelve resultados sin
relacion con la obra consultada.
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

from adviser.domain import recent_seeds, recommend_from_history  # noqa: E402
from adviser.domain.history import DEFAULT_MAX_PER_SEED, DEFAULT_MIN_SCORE  # noqa: E402
from adviser.domain.index import SimilarityIndex  # noqa: E402
from adviser.storage import load  # noqa: E402
from rpc_http import DEFAULT_CONFIG, RpcError, transport_from_file  # noqa: E402

TMDB_PATH = ("plugin://plugin.video.themoviedb.helper/"
             "?info=recommendations&tmdb_type=movie&tmdb_id=%s")


def catalogue(call):
    """`{movieid: (titulo, tmdb)}` y `{tmdb: movieid}` de toda la videoteca."""
    result = call("VideoLibrary.GetMovies",
                  {"properties": ["title", "uniqueid", "playcount", "lastplayed"]}) or {}
    movies = result.get("movies") or []
    by_id = {}
    by_tmdb = {}
    for movie in movies:
        tmdb = (movie.get("uniqueid") or {}).get("tmdb")
        by_id[movie["movieid"]] = (movie.get("title"), tmdb)
        if tmdb:
            by_tmdb[str(tmdb)] = movie["movieid"]
    return movies, by_id, by_tmdb


def tmdb_recommendations(call, tmdb_id, by_tmdb, limit):
    """Recomendaciones de TMDB, separando lo que esta en catalogo de lo que no."""
    try:
        result = call("Files.GetDirectory",
                      {"directory": TMDB_PATH % tmdb_id, "media": "video",
                       "properties": ["title", "uniqueid"]}) or {}
    except Exception as error:  # noqa: BLE001 - el complemento puede fallar o faltar
        return [("(TMDB no respondio: %s)" % error, False)]
    rows = []
    for entry in (result.get("files") or []):
        identifier = (entry.get("uniqueid") or {}).get("tmdb")
        if identifier is None:
            continue
        movie_id = by_tmdb.get(str(identifier))
        rows.append((entry.get("label"), movie_id is not None))
        if len(rows) >= limit:
            break
    return rows


def _columns(left, right, width=44):
    height = max(len(left), len(right))
    for row in range(height):
        a = left[row] if row < len(left) else ""
        b = right[row] if row < len(right) else ""
        print("  %-*s %s" % (width, a[:width], b[:width]))


def compare(call, index, titles, by_id, by_tmdb, movie_id, limit, min_score):
    title, tmdb = by_id.get(movie_id, ("?", None))
    print("\n" + "=" * 92)
    print("%s   [movieid=%s tmdb=%s]" % (title, movie_id, tmdb))
    print("=" * 92)

    local = ["%2d. %s  (%.3f)" % (n + 1, titles.get(str(other), other), score)
             for n, (other, score) in
             enumerate(index.neighbours(movie_id, limit=limit, min_score=min_score))]
    if not local:
        local = ["(el motor local calla: nada supera el umbral %.2f)" % min_score]

    if tmdb:
        remote = ["%2d. %s%s" % (n + 1, label, "" if owned else "   [no la tienes]")
                  for n, (label, owned) in
                  enumerate(tmdb_recommendations(call, tmdb, by_tmdb, limit))]
    else:
        remote = ["(sin identificador de TMDB)"]

    print("  %-44s %s" % ("MOTOR LOCAL (catalogo propio)", "TMDB recommendations"))
    print("  %-44s %s" % ("-" * 44, "-" * 44))
    _columns(local, remote)


def identity_map(movies):
    """Identidad real de cada obra, para que un duplicado no cuente dos veces.

    Se prefiere el identificador externo; cuando no lo hay, titulo y ano
    normalizados. Si no hay ni una cosa ni la otra, se devuelve `None` y esa ficha
    no se deduplica: degradar es preferible a descartar por sospecha.
    """
    keys = {}
    for movie in movies:
        unique = (movie.get("uniqueid") or {}).get("tmdb")
        if unique:
            keys[movie["movieid"]] = ("tmdb", str(unique))
            continue
        title = movie.get("title")
        if title:
            keys[movie["movieid"]] = ("title", " ".join(str(title).split()).lower(),
                                      movie.get("year"))
    return keys.get


def show_history(index, titles, movies, limit, include_unfinished,
                 min_score=DEFAULT_MIN_SCORE, max_per_seed=DEFAULT_MAX_PER_SEED):
    seeds = recent_seeds(movies, include_unfinished=include_unfinished)
    print("\n" + "=" * 92)
    print("FILA «PORQUE VISTE…»  (%d semillas%s)"
          % (len(seeds), ", incluyendo lo empezado y no acabado" if include_unfinished else ""))
    print("=" * 92)
    if not seeds:
        print("  No hay historial de reproduccion en esta biblioteca.")
        return
    for item_id, weight in seeds:
        print("  semilla  %-52s peso %.2f" % (titles.get(str(item_id), item_id), weight))
    watched = {m["movieid"] for m in movies if m.get("playcount")}
    print("  (umbral %.2f, tope %d por semilla)" % (min_score, max_per_seed))
    print()
    for n, (other, score, because) in enumerate(
            recommend_from_history(index, seeds, limit=limit, exclude=watched,
                                   min_score=min_score, max_per_seed=max_per_seed,
                                   key_of=identity_map(movies))):
        print("  %2d. %-50s (%.3f)  porque viste %s"
              % (n + 1, titles.get(str(other), other), score,
                 titles.get(str(because), because)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="fichero con las credenciales del JSON-RPC")
    parser.add_argument("--from-file", help="volcado JSON del catalogo; no consulta a Kodi "
                                            "ni a TMDB, util para evaluar otro nodo")
    parser.add_argument("--index", default="indice/movies.json")
    parser.add_argument("--sample", type=int, default=5, help="cuantas peliculas comparar")
    parser.add_argument("--title", action="append", help="comparar una pelicula concreta")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--history", action="store_true", help="evaluar la fila «porque viste…»")
    parser.add_argument("--include-unfinished", action="store_true",
                        help="cuenta tambien lo empezado y no acabado")
    parser.add_argument("--seed", type=int, default=None, help="semilla para una muestra repetible")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="umbral de confianza; por debajo el motor calla")
    parser.add_argument("--max-per-seed", type=int, default=DEFAULT_MAX_PER_SEED,
                        help="cuantos huecos puede ocupar una misma semilla")
    args = parser.parse_args(argv)

    try:
        payload = load(args.index)
    except OSError as error:
        print("No se pudo leer el indice: %s" % error, file=sys.stderr)
        print("Construyelo antes con: python3 tools/build_index.py --output %s"
              % args.index, file=sys.stderr)
        return 2
    index = SimilarityIndex.from_dict(payload)
    titles = payload.get("titles") or {}
    if args.from_file:
        # Volcado de otro equipo. Permite evaluar su catalogo y su historial sin
        # necesitar aqui sus credenciales. Sin Kodi al otro
        # lado no hay comparacion con TMDB: solo motor local e historial.
        with open(args.from_file, encoding="utf-8") as handle:
            movies = json.load(handle)
        for entry in movies:
            entry.setdefault("id", entry.get("movieid"))
        by_id = {m["movieid"]: (m.get("title"), None) for m in movies}
        by_tmdb = {}
        call = None
    else:
        try:
            call = transport_from_file(args.config)
        except (OSError, RpcError) as error:
            print("No se pudo leer la configuracion del JSON-RPC: %s" % error, file=sys.stderr)
            print("Se esperaba un fichero como %s con KODI_URL, KODI_USER y "
                  "KODI_PASS." % DEFAULT_CONFIG, file=sys.stderr)
            return 2
        movies, by_id, by_tmdb = catalogue(call)

    if args.history:
        show_history(index, titles, movies, args.limit, args.include_unfinished,
                     min_score=args.min_score, max_per_seed=args.max_per_seed)
        return 0

    if args.title:
        wanted = []
        for needle in args.title:
            found = [i for i, (t, _) in by_id.items() if t and needle.lower() in t.lower()]
            if not found:
                print("sin coincidencias para %r" % needle)
            wanted.extend(found[:1])
    else:
        rng = random.Random(args.seed)
        pool = [i for i in by_id if index.features_of(i)]
        wanted = rng.sample(pool, min(args.sample, len(pool)))

    for movie_id in wanted:
        compare(call, index, titles, by_id, by_tmdb, movie_id, args.limit, args.min_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
