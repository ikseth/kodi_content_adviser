"""Transporte JSON-RPC por HTTP, **solo para desarrollo**.

El addon no usara esto: dentro de Kodi se habla por `xbmc.executeJSONRPC()` en
proceso, que no necesita servidor web ni abre puertos. Esto existe para poder
construir y evaluar el motor desde fuera, contra un Kodi real.

La configuracion se lee de un fichero que **vive fuera del repositorio**, porque
lleva la contrasena del servidor web. Formato:

    KODI_URL=http://127.0.0.1:8080/jsonrpc
    KODI_USER=kodi
    KODI_PASS=...
"""

import base64
import json
import os
import urllib.request

__all__ = ["transport_from_file", "DEFAULT_CONFIG"]

DEFAULT_CONFIG = os.path.expanduser("~/kodi-adviser-dev/jsonrpc.env")


class RpcError(RuntimeError):
    pass


def _read_config(path):
    settings = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    missing = [k for k in ("KODI_URL", "KODI_USER", "KODI_PASS") if k not in settings]
    if missing:
        raise RpcError("faltan claves en %s: %s" % (path, ", ".join(missing)))
    return settings


def transport_from_file(path=None, timeout=600):
    """Devuelve un `call(method, params) -> result` listo para `LibraryReader`."""
    settings = _read_config(path or DEFAULT_CONFIG)
    credentials = "%s:%s" % (settings["KODI_USER"], settings["KODI_PASS"])
    header = "Basic " + base64.b64encode(credentials.encode()).decode()
    url = settings["KODI_URL"]

    def call(method, params=None):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        request = urllib.request.Request(
            url, json.dumps(payload).encode(),
            {"Content-Type": "application/json", "Authorization": header})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
        if body.get("error"):
            raise RpcError("%s: %s" % (method, body["error"]))
        return body.get("result")

    return call
