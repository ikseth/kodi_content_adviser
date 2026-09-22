"""Capa adaptador: **todo lo que toca Kodi vive aqui**.

`lib/adviser/` es el nucleo y no importa `xbmc` en ningun punto. Esa frontera es
lo que permite construir y evaluar el motor sin Kodi delante, y hay una prueba que
la vigila. Aqui se cruza a proposito y en un solo sitio.
"""

import json
import os

import xbmc
import xbmcaddon
import xbmcvfs

ADDON_ID = "plugin.video.content.adviser"

__all__ = ["Addon", "log", "rpc", "data_path", "localise"]


def _addon():
    return xbmcaddon.Addon(ADDON_ID)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, message), level)


def rpc(method, params=None):
    """JSON-RPC en proceso.

    `xbmc.executeJSONRPC` no requiere tener activado el servidor web de Kodi: el
    addon habla con Kodi por dentro y no hay que abrir ningun puerto.
    """
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    except (ValueError, TypeError) as error:
        log("respuesta JSON-RPC invalida en %s: %s" % (method, error), xbmc.LOGERROR)
        return None
    if response.get("error"):
        log("JSON-RPC %s: %s" % (method, response["error"]), xbmc.LOGERROR)
        return None
    return response.get("result")


def data_path(*parts):
    """Ruta dentro de `addon_data`, creada si hace falta.

    Siempre por `xbmcvfs.translatePath`: entre LibreELEC, Recalbox y Android no hay
    ninguna ruta de disco concreta que valga en las tres.
    """
    base = xbmcvfs.translatePath(_addon().getAddonInfo("profile"))
    if not xbmcvfs.exists(base):
        xbmcvfs.mkdirs(base)
    return os.path.join(base, *parts)


def localise(string_id):
    return _addon().getLocalizedString(string_id)


class Addon:
    """Lectura de ajustes, con el tipo que corresponde a cada uno."""

    def __init__(self):
        self._addon = _addon()

    def _number(self, key, fallback):
        try:
            return float(self._addon.getSetting(key))
        except (TypeError, ValueError):
            return fallback

    def _integer(self, key, fallback):
        try:
            return int(float(self._addon.getSetting(key)))
        except (TypeError, ValueError):
            return fallback

    def _flag(self, key, fallback=False):
        value = self._addon.getSetting(key)
        if value in ("true", "false"):
            return value == "true"
        return fallback

    @property
    def min_score(self):
        return self._number("min_score", 0.10)

    @property
    def max_per_seed(self):
        return self._integer("max_per_seed", 2)

    @property
    def seed_count(self):
        return self._integer("seed_count", 10)

    @property
    def result_count(self):
        return self._integer("result_count", 20)

    @property
    def include_unfinished(self):
        return self._flag("include_unfinished", False)

    @property
    def rich_index(self):
        return self._flag("rich_index", True)

    @property
    def suggestion_count(self):
        return self._integer("suggestion_count", 9)

    @property
    def use_external(self):
        return self._flag("use_external", True)

    @property
    def show_outside_catalogue(self):
        return self._flag("show_outside_catalogue", True)

    @property
    def ai_enabled(self):
        return self._flag("ai_enabled", False)

    @property
    def ai_provider(self):
        # El ajuste es una lista; el valor guardado es el identificador del
        # dialecto, no un indice, para que anadir proveedores no reordene nada.
        return self._addon.getSetting("ai_provider") or "openai_compatible"

    @property
    def ai_base_url(self):
        return (self._addon.getSetting("ai_base_url") or "").strip()

    @property
    def ai_model(self):
        return (self._addon.getSetting("ai_model") or "").strip()

    @property
    def ai_user_id(self):
        return (self._addon.getSetting("ai_user_id") or "").strip() or "kodi.gg"

    @property
    def ai_api_key(self):
        return (self._addon.getSetting("ai_api_key") or "").strip()

    @property
    def rebuild_on_scan(self):
        return self._flag("rebuild_on_scan", True)
