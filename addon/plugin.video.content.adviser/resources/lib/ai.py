"""Llamada al servicio de IA. Es la unica parte que toca la red.

Con `urllib` de la libreria estandar: un addon solo puede depender de modulos que
existan en un repositorio de Kodi, y para un `POST` con JSON no hace falta nada
mas.

**Timeout explicito y un reintento con espera.** Un servicio que no contesta no
puede colgar el hilo ni el apagado de Kodi. Y como esto se invoca por peticion
expresa del usuario, fallar rapido y decirlo es mejor que esperar indefinidamente.
"""

import json
import time
import urllib.error
import urllib.request

import xbmc
from adviser.ai import build_prompt, build_request, parse_query, parse_response
from adviser.ai.providers import ProviderError
from adviser.ai.query import SYSTEM_PROMPT

from .bridge import log, rpc

__all__ = ["ask", "genres", "identity_of", "AiError"]

# Quien pregunta, visto desde el servicio. El usuario es configurable porque en
# una casa con varios equipos puede interesar distinguirlos; el servicio no, que
# es esto y no cambia.
SERVICE_NAME = "kodi.content.adviser"
SESSION_PROPERTY = "adviser.session_id"

# Medido contra un Ollama real: con el modelo ya cargado, una consulta tarda menos
# de un segundo; **la primera, con el modelo frio, tardo 42,8 s**. Un margen corto
# convertiria ese primer uso en un fallo, y el usuario concluiria que no funciona.
TIMEOUT = 75
RETRY_WAIT = 2.0


class AiError(RuntimeError):
    pass


def genres(media_type="movie"):
    """Los generos que el catalogo tiene de verdad.

    Se le pasan al modelo para que elija de un menu cerrado en vez de acertar el
    vocabulario: un genero inventado no filtra nada y se colaria hasta la pantalla.
    """
    result = rpc("VideoLibrary.GetGenres", {"type": media_type}) or {}
    return [g["label"] for g in (result.get("genres") or []) if g.get("label")]


def identity_of(settings):
    """Identidad para los servicios que la piden.

    La sesion la publica el servicio al arrancar, asi que **dura lo que dura este
    Kodi**: es el alcance natural para que el otro lado pueda relacionar varias
    preguntas de la misma tarde sin arrastrar las del mes pasado.
    """
    import xbmcgui
    sesion = xbmcgui.Window(10000).getProperty(SESSION_PROPERTY)
    return {"user_id": settings.ai_user_id,
            "service": SERVICE_NAME,
            "session_id": sesion or "sin-sesion"}


def _post(url, headers, body):
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, payload, headers)
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Un 4xx no mejora esperando: es la peticion, no el momento.
            detail = error.read()[:300].decode("utf-8", "replace")
            raise AiError("%s: %s" % (error.code, detail)) from None
        except (urllib.error.URLError, OSError, ValueError) as error:
            last = error
            if attempt == 0:
                log("el servicio de IA no respondio (%s); se reintenta" % error,
                    xbmc.LOGWARNING)
                time.sleep(RETRY_WAIT)
    raise AiError(str(last))


def ask(settings, request_text, media_type="movie"):
    """Traduce una frase a una consulta estructurada. Devuelve `(Query, generos)`."""
    catalogue_genres = genres(media_type)
    try:
        url, headers, body = build_request(
            settings.ai_provider, settings.ai_base_url, settings.ai_model,
            SYSTEM_PROMPT, build_prompt(request_text, catalogue_genres, media_type),
            api_key=settings.ai_api_key, identity=identity_of(settings))
    except ProviderError as error:
        raise AiError(str(error)) from None

    answer = _post(url, headers, body)
    try:
        text = parse_response(settings.ai_provider, answer)
        return parse_query(text, catalogue_genres), catalogue_genres
    except (ProviderError, ValueError) as error:
        raise AiError(str(error)) from None
