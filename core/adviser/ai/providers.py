"""Los dialectos de los proveedores, sin tocar la red.

Aqui solo se construye la peticion y se lee la respuesta. El HTTP vive en la capa
adaptador, y esa separacion es lo que permite probar los dos dialectos sin
servidor delante ni conexion.

**Un solo adaptador cubre casi todo.** Ollama y OpenAI hablan el mismo dialecto
(`/chat/completions`), asi que el proveedor por defecto los cubre con tres
ajustes: URL, modelo y clave. Claude e IA_NEST no siguen ese dialecto y entran
como **un adaptador mas cada uno**, no como casos especiales repartidos por el
codigo. Anadir el cuarto sera tocar solo este fichero.
"""

__all__ = ["OPENAI_COMPATIBLE", "ANTHROPIC", "IA_NEST", "PROVIDERS",
           "build_request", "parse_response", "ProviderError"]

OPENAI_COMPATIBLE = "openai_compatible"
ANTHROPIC = "anthropic"
IA_NEST = "ia_nest"
PROVIDERS = (OPENAI_COMPATIBLE, ANTHROPIC, IA_NEST)

DEFAULT_MAX_TOKENS = 512


class ProviderError(RuntimeError):
    pass


def _join(base_url, path):
    return "%s/%s" % (base_url.rstrip("/"), path.lstrip("/"))


def build_request(provider, base_url, model, system, user, api_key=None,
                  max_tokens=DEFAULT_MAX_TOKENS, identity=None):
    """Devuelve `(url, cabeceras, cuerpo)` listos para enviar."""
    if not base_url:
        raise ProviderError("falta la URL del servicio")
    if not model and provider != IA_NEST:
        # En IA_NEST el modelo es opcional: lo elige su router por dominio, que es
        # justo la razon de ser de ese servicio.
        raise ProviderError("falta el modelo")

    headers = {"Content-Type": "application/json"}

    if provider == OPENAI_COMPATIBLE:
        # Ollama no pide clave; OpenAI y compatibles si. Se manda solo si la hay,
        # en vez de inventarse una de relleno.
        if api_key:
            headers["Authorization"] = "Bearer %s" % api_key
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        return _join(base_url, "chat/completions"), headers, body

    if provider == ANTHROPIC:
        if not api_key:
            raise ProviderError("este proveedor necesita una clave")
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        return _join(base_url, "v1/messages"), headers, body

    if provider == IA_NEST:
        # `prompt.run` recibe **un solo prompt**, no una conversacion con papeles.
        # Se unen las dos partes en vez de tirar la de sistema, que es la que
        # fija el formato de la respuesta.
        body = {"prompt": "%s\n\n%s" % (system, user), "domain": "general"}
        if model:
            body["model"] = model
        if identity:
            # **Tiene que ser un objeto**: comprobado contra el servicio real,
            # una cadena da `identity debe ser un objeto`. Lleva quien pregunta,
            # desde donde, y una sesion, que es lo que permite a ese servicio
            # relacionar varias preguntas entre si.
            body["identity"] = dict(identity)
        return _join(base_url, "prompt/run"), headers, body

    raise ProviderError("proveedor desconocido: %r" % (provider,))


def parse_response(provider, payload):
    """Saca el texto de la respuesta, sea cual sea el dialecto."""
    if not isinstance(payload, dict):
        raise ProviderError("respuesta que no es un objeto")

    if payload.get("error"):
        raise ProviderError(str(payload["error"]))

    if provider == OPENAI_COMPATIBLE:
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError("respuesta sin contenido")
        return ((choices[0].get("message") or {}).get("content") or "").strip()

    if provider == ANTHROPIC:
        blocks = payload.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
        if not text:
            raise ProviderError("respuesta sin contenido")
        return text.strip()

    if provider == IA_NEST:
        text = (payload.get("response") or "").strip()
        if not text:
            raise ProviderError("respuesta sin contenido")
        return text

    raise ProviderError("proveedor desconocido: %r" % (provider,))
