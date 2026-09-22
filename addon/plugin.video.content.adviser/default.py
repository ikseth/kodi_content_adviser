"""Punto de entrada del listado.

Rutas:
    plugin://plugin.video.content.adviser/                      menu raiz
    plugin://plugin.video.content.adviser/?action=history       fila «porque viste…»
    plugin://plugin.video.content.adviser/?action=similar&dbid=N
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from urllib.parse import parse_qsl, quote_plus

import xbmcgui
import xbmcplugin  # noqa: I001
from adviser.domain import combine, recent_seeds, recommend_from_history
from adviser.domain.blend import LIBRARY
from resources.lib import catalogue, external
from resources.lib.bridge import Addon, localise, log, rpc
from resources.lib.listing import render, render_tvshows


def _watched_movies():
    result = rpc("VideoLibrary.GetMovies",
                 {"properties": ["playcount", "lastplayed"]}) or {}
    movies = result.get("movies") or []
    for movie in movies:
        movie.setdefault("id", movie.get("movieid"))
    return movies


def _ai_available():
    """Si la capa de IA viaja en este paquete.

    La variante sin IA **no la lleva**: ni codigo, ni ajustes, ni textos. Es la
    misma garantia estructural que usa el proyecto hermano con su suscriptor, y
    por eso se comprueba importando, no preguntando a un ajuste.
    """
    try:
        from resources.lib import ai  # noqa: F401
    except ImportError:
        return False
    return True


def _root(handle, base, settings):
    entradas = [(30001, "history", "DefaultMovies.png")]
    if settings.use_external and not external.installed():
        # La fuente externa esta pedida pero no esta instalada. Se ofrece
        # instalarla en vez de dejar que el usuario la busque a mano.
        entradas.append((30003, "install_external", "DefaultAddonProgram.png"))
    if settings.ai_enabled and _ai_available():
        # Solo se ofrece si hay servicio configurado: una entrada que siempre
        # contesta «no esta activado» es ruido en el menu.
        entradas.append((30002, "ask", "DefaultAddonsSearch.png"))
    for etiqueta, accion, icono in entradas:
        entry = xbmcgui.ListItem(label=localise(etiqueta))
        entry.setArt({"icon": icono})
        xbmcplugin.addDirectoryItem(handle, "%s?action=%s" % (base, accion),
                                    entry, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def _empty(handle, message_id, detail=None):
    """Un listado vacio con explicacion.

    El motor calla cuando no tiene nada con suficiente confianza, y callar sin
    decir por que parece una averia.
    """
    texto = localise(message_id)
    if detail:
        texto = "%s  (%s)" % (texto, detail)
    entry = xbmcgui.ListItem(label=texto)
    entry.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(handle, "", entry, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _history(handle, settings):
    index, titles, identity = catalogue.read_index()
    if index is None:
        return _empty(handle, 30030)
    movies = _watched_movies()
    seeds = recent_seeds(movies, limit=settings.seed_count,
                         include_unfinished=settings.include_unfinished)
    if not seeds:
        return _empty(handle, 30031)
    watched = {m["movieid"] for m in movies if m.get("playcount")}
    rows = recommend_from_history(index, seeds, limit=settings.result_count,
                                  exclude=watched, min_score=settings.min_score,
                                  max_per_seed=settings.max_per_seed,
                                  key_of=catalogue.identity_map(identity))
    if not rows:
        return _empty(handle, 30032)
    # La fila de inicio no consulta la fuente externa: serian tantas peticiones de
    # red como semillas, y esta fila tiene que pintarse ya.
    entries = [(LIBRARY, movie_id, None) for movie_id, _score, _because in rows]
    reasons = {movie_id: titles.get(str(because)) for movie_id, _score, because in rows}
    render(handle, entries, titles, reasons=reasons)


# Marca que el teclado se ha abierto para preguntar a la IA. El skin alimenta el
# panel de sugerencias con la misma ruta para cualquier teclado, asi que hay que
# distinguirlo aqui: completar un titulo y componer una pregunta no se parecen.
ASK_FLAG = "adviser_asking"


def _asking():
    """Devuelve la clase de obra que se esta pidiendo, o `None` si no se pregunta.

    La marca **lleva el tipo**, no un simple «si»: componer una pregunta sobre
    series con el vocabulario de las peliculas no ayuda a nadie.
    """
    return xbmcgui.Window(10000).getProperty(ASK_FLAG) or None


def _autocomplete(handle, base, settings, query):
    """Sugerencias para el teclado virtual de Kodi.

    El panel de autocompletado de Estuary se alimenta de un listado `plugin://`,
    igual que el complemento oficial. Cada sugerencia apunta de vuelta a este
    mismo addon, que es quien escribe el texto en el teclado: un listado no puede
    teclear por si solo.
    """
    clase_pedida = _asking()
    if clase_pedida:
        # Componer, no completar. Lo que se manda al teclado es la frase entera
        # resultante, porque `Input.SendText` fija el texto: se puede, y ademas
        # asi lo que se lee en la lista es exactamente lo que quedara escrito.
        libro = catalogue.read_phrasebook(clase_pedida)
        suggestions = libro.suggest(query, limit=settings.suggestion_count,
                                    history=catalogue.read_questions()) if libro else []
        clase = "phrase"
    else:
        # **`PrefixIndex.suggest` devuelve `(texto, clase)`, no `(valor,
        # etiqueta)`.** Son dos formas distintas en la misma posicion, y darlas
        # por iguales pinto la palabra «title» en la lista en vez del titulo.
        # Se convierte aqui y explicito: para un termino, lo que se manda y lo
        # que se lee son lo mismo.
        prefix = catalogue.read_prefix(query)
        encontrados = prefix.suggest(query, limit=settings.suggestion_count) if prefix else []
        suggestions = [(texto, texto) for texto, _clase in encontrados]
        clase = "term"

    items = []
    for value, label in suggestions:
        entry = xbmcgui.ListItem(label=label)
        entry.setProperty("adviser_suggestion_kind", clase)
        items.append(("%s?action=pick&text=%s" % (base, quote_plus(value)), entry, False))
    if items:
        xbmcplugin.addDirectoryItems(handle, items, len(items))
    # Sin `endOfDirectory` el contenedor del teclado se queda girando.
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _pick(handle, text):
    """Escribe en el teclado la sugerencia elegida.

    Se resuelve la URL como fallida a proposito: no hay nada que reproducir. Lo
    unico que se quiere es meter el texto donde el usuario estaba escribiendo.
    """
    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
    rpc("Input.SendText", {"text": text, "done": False})


def _search(handle, settings, query):
    """Resultados de biblioteca para un termino: titulo, director o reparto."""
    condition = {"or": [
        {"field": "title", "operator": "contains", "value": query},
        {"field": "actor", "operator": "contains", "value": query},
        {"field": "director", "operator": "contains", "value": query},
    ]}
    result = rpc("VideoLibrary.GetMovies",
                 {"filter": condition, "properties": ["title"],
                  "limits": {"start": 0, "end": settings.result_count}}) or {}
    movies = result.get("movies") or []
    if not movies:
        return _empty(handle, 30035)
    entries = [(LIBRARY, m["movieid"], None) for m in movies]
    titles = {str(m["movieid"]): m.get("title") for m in movies}
    render(handle, entries, titles)


# Que sabe contestar cada tipo. Las series no tienen duracion -no es un dato de
# la serie, sino de cada episodio-, asi que ese filtro no se les aplica.
ASK_TYPES = {
    "movie": ("VideoLibrary.GetMovies", "movies", True),
    "tvshow": ("VideoLibrary.GetTVShows", "tvshows", False),
}


def _ask(handle, settings, pregunta=None, media_type="movie"):
    """Pregunta en lenguaje natural. **Peticion expresa del usuario**, nunca automatica.

    El modelo no nombra peliculas: traduce la frase a un filtro y **es el catalogo
    quien contesta**. Lo peor que puede pasar es que no encuentre nada, no que
    ofrezca lo que no se tiene.
    """
    if not _ai_available():
        # No deberia llegarse aqui: sin la capa, la entrada ni se ofrece. Pero una
        # ruta invocada a mano o desde un favorito antiguo no puede reventar.
        return _empty(handle, 30035)
    from adviser.ai import to_library_filter, to_sort
    from resources.lib import ai

    if not settings.ai_enabled:
        return _empty(handle, 30036)

    # La pregunta puede venir en la ruta. Sirve para guardar un favorito con una
    # consulta fija -«algo corto y de risa»- y para poder probar sin teclado.
    if not pregunta:
        ventana = xbmcgui.Window(10000)
        ventana.setProperty(ASK_FLAG, media_type)
        try:
            pregunta = xbmcgui.Dialog().input(localise(30037))
        finally:
            # Si se queda puesta, el buscador de titulos empezaria a sugerir
            # frases. Se limpia pase lo que pase.
            ventana.clearProperty(ASK_FLAG)
    if not pregunta:
        return xbmcplugin.endOfDirectory(handle, succeeded=False)
    catalogue.remember_question(pregunta)

    progreso = xbmcgui.DialogProgressBG()
    progreso.create(localise(30000), localise(30038))
    try:
        consulta, _ = ai.ask(settings, pregunta, media_type)
    except ai.AiError as error:
        # El registro ya decia la causa y la pantalla no. Un «no ha contestado»
        # cuando el servicio contesto «no conozco ese modelo» manda a buscar el
        # fallo donde no esta.
        motivo = " ".join(str(error).split())[:120]
        log("la consulta a la IA fallo: %s" % error)
        xbmcgui.Dialog().notification(localise(30000), motivo or localise(30039))
        return _empty(handle, 30039, motivo)
    finally:
        progreso.close()

    # «No entendi lo que pides» y «no tienes nada asi» son cosas distintas, y
    # con el mismo mensaje no hay forma de saber cual paso ni donde mirar.
    resumen = ", ".join("%s=%s" % (k, v) for k, v in sorted(vars(consulta).items()) if v)
    log("pregunta %r -> %s" % (pregunta, resumen or "(nada aplicable)"))
    if consulta.is_empty:
        return _empty(handle, 30042)

    metodo, clave, admite_duracion = ASK_TYPES.get(media_type, ASK_TYPES["movie"])
    if not admite_duracion:
        consulta.max_runtime = None

    propiedades = (["title"] if clave == "movies"
                   else ["title", "year", "plot", "rating", "art", "genre"])
    params = {"properties": propiedades,
              "limits": {"start": 0, "end": settings.result_count}}
    filtro = to_library_filter(consulta)
    if filtro:
        params["filter"] = filtro
    orden = to_sort(consulta)
    if orden:
        params["sort"] = orden

    encontrados = ((rpc(metodo, params) or {}).get(clave)) or []
    if not encontrados:
        return _empty(handle, 30035, resumen)
    if clave == "tvshows":
        return render_tvshows(handle, encontrados)
    entries = [(LIBRARY, m["movieid"], None) for m in encontrados]
    render(handle, entries, {str(m["movieid"]): m.get("title") for m in encontrados})


def _similar(handle, settings, dbid):
    index, titles, identity = catalogue.read_index()
    if index is None:
        return _empty(handle, 30030)
    dbid = int(dbid)
    local = index.neighbours(dbid, limit=settings.result_count,
                             min_score=settings.min_score)

    # El motor local tiene respuesta confiable para una parte del catalogo y calla
    # para el resto. Ahi, y solo ahi, se pregunta fuera.
    remote = []
    if settings.use_external and len(local) < settings.result_count:
        tmdb = catalogue.tmdb_of(identity, dbid)
        if tmdb and external.available():
            remote = external.recommendations(tmdb, limit=settings.result_count)
        elif tmdb:
            log("fuente externa pedida pero %s no esta activo" % external.HELPER_ID)

    entries = combine(local, remote, settings.result_count,
                      catalogue.tmdb_resolver(identity), exclude={dbid},
                      include_outside=settings.show_outside_catalogue)
    if not entries:
        return _empty(handle, 30032)
    render(handle, entries, titles)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    # Se leen aqui y no en el modulo: con `reuselanguageinvoker` el interprete se
    # reutiliza entre invocaciones y el modulo **no se vuelve a importar**, asi que
    # cualquier estado de nivel de modulo se quedaria congelado en la primera
    # llamada. Es el fallo clasico de esa opcion.
    handle = int(argv[1]) if len(argv) > 1 else -1
    base = argv[0] if argv else ""
    params = dict(parse_qsl((argv[2] if len(argv) > 2 else "").lstrip("?")))
    action = params.get("action")
    settings = Addon()
    if action == "history":
        _history(handle, settings)
    elif action == "similar" and params.get("dbid"):
        _similar(handle, settings, params["dbid"])
    elif action == "autocomplete":
        _autocomplete(handle, base, settings, params.get("q") or params.get("id") or "")
    elif action == "pick":
        _pick(handle, params.get("text") or "")
    elif action == "install_external":
        external.offer_install()
        xbmcplugin.endOfDirectory(handle, succeeded=False)
    elif action == "ask":
        _ask(handle, settings, params.get("q"), params.get("type") or "movie")
    elif action == "search" and params.get("q"):
        _search(handle, settings, params["q"])
    else:
        _root(handle, base, settings)
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - un fallo aqui no puede colgar la interfaz
        log("fallo al construir el listado: %s" % error)
        xbmcplugin.endOfDirectory(int(sys.argv[1]) if len(sys.argv) > 1 else -1,
                                  succeeded=False)
