"""Entrada de menu contextual «Similares a esta».

Abre el listado del propio addon con el item enfocado como referencia. No hace el
calculo aqui: el menu contextual tiene que cerrarse rapido.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import xbmc  # noqa: E402
import xbmcgui  # noqa: E402
from resources.lib.bridge import ADDON_ID, localise, log  # noqa: E402


def main():
    dbid = xbmc.getInfoLabel("ListItem.DBID")
    dbtype = xbmc.getInfoLabel("ListItem.DBTYPE")
    if not dbid or dbid == "-1":
        xbmcgui.Dialog().notification(localise(30000), localise(30033))
        return
    if dbtype != "movie":
        # Series todavia no: el indice que se construye es de peliculas. Decirlo
        # es mejor que abrir un listado vacio.
        xbmcgui.Dialog().notification(localise(30000), localise(30034))
        return
    ruta = "plugin://%s/?action=similar&dbid=%s" % (ADDON_ID, dbid)
    log("menu contextual -> %s" % ruta)
    xbmc.executebuiltin('ActivateWindow(videos,"%s",return)' % ruta)


if __name__ == "__main__":
    main()
