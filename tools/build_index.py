"""Construye el indice de similitud contra un Kodi real y lo guarda.

    python3 tools/build_index.py --output indice/movies.json
    python3 tools/build_index.py --output indice/movies.json --rich

Se mide cada fase por separado, porque el reparto entre fase basica y enriquecida
es lo que decide si el recomendador es usable en el nodo mas lento.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

from adviser.domain import FeatureExtractor, SimilarityIndex  # noqa: E402
from adviser.library import BASIC_MOVIE_FIELDS, RICH_MOVIE_FIELDS, LibraryReader  # noqa: E402
from adviser.storage import save  # noqa: E402
from rpc_http import DEFAULT_CONFIG, RpcError, transport_from_file  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="fichero con las credenciales del JSON-RPC")
    parser.add_argument("--from-file", help="volcado JSON del catalogo, en vez de consultar Kodi")
    parser.add_argument("--output", default="indice/movies.json", help="donde guardar el indice")
    parser.add_argument("--rich", action="store_true",
                        help="anade la fase cara (reparto e identificadores)")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--cast-depth", type=int, default=10)
    args = parser.parse_args(argv)

    started = time.time()
    if args.from_file:
        # Volcado de otro nodo: permite indexar el catalogo de un equipo de la
        # flota sin necesitar aqui sus credenciales.
        with open(args.from_file, encoding="utf-8") as handle:
            items = json.load(handle)
        for item in items:
            item.setdefault("id", item.get("movieid"))
    else:
        try:
            call = transport_from_file(args.config)
        except (OSError, RpcError) as error:
            print("No se pudo leer la configuracion del JSON-RPC: %s" % error, file=sys.stderr)
            print("Se esperaba un fichero como %s con KODI_URL, KODI_USER y "
                  "KODI_PASS." % DEFAULT_CONFIG, file=sys.stderr)
            return 2
        fields = list(BASIC_MOVIE_FIELDS)
        if args.rich:
            fields += list(RICH_MOVIE_FIELDS)
        items = LibraryReader(call, page_size=args.page_size).read("movie", fields)
    read_seconds = time.time() - started
    origen = args.from_file or ("fase basica + enriquecida" if args.rich else "fase basica")
    print("leidas %d peliculas en %.2f s (%s)" % (len(items), read_seconds, origen))

    started = time.time()
    index = SimilarityIndex.build(items, FeatureExtractor(cast_depth=args.cast_depth))
    build_seconds = time.time() - started
    print("indice construido: %d items indexados en %.2f s" % (index.size, build_seconds))

    payload = index.to_dict()
    payload["titles"] = {str(i["id"]): i.get("title") for i in items if i.get("id") is not None}
    payload["rich"] = args.rich
    save(args.output, payload)
    print("guardado en %s (%.1f MB)"
          % (args.output, os.path.getsize(args.output) / 1048576.0))
    print("total %.2f s" % (read_seconds + build_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
