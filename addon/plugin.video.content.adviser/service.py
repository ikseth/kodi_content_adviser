"""Servicio: mantiene el indice al dia sin que se note.

Se construye **en segundo plano y nunca en un camino de interfaz**: medido en una
Raspberry Pi 4 con biblioteca MySQL, la fase basica cuesta unos 2 s y la
enriquecida unos 50. Lo segundo es asumible mientras nadie lo este esperando.

Se reconstruye **por evento** —cuando Kodi termina de escanear o actualiza la
biblioteca— y no por reloj: un temporizador reconstruiria sin motivo la mayoria de
las veces y no reaccionaria cuando de verdad hace falta.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import xbmc  # noqa: E402
import xbmcgui  # noqa: E402
from resources.lib import catalogue  # noqa: E402
from resources.lib.bridge import Addon, log  # noqa: E402

# El skin no puede leer un ajuste del complemento, asi que el estado se publica
# en una propiedad de la ventana de inicio. Es el mismo mecanismo que usa
# `kodi-addon-cec` para que el sistema domotico conozca el estado del televisor.
ASK_READY = "adviser.ask_ready"
SESSION_PROPERTY = "adviser.session_id"


def _publish_session():
    """Una sesion por arranque de Kodi.

    Los servicios de IA con memoria la usan para relacionar varias preguntas
    entre si. El arranque es el alcance natural: las de esta tarde van juntas y
    las del mes pasado no se arrastran.
    """
    import uuid
    xbmcgui.Window(10000).setProperty(SESSION_PROPERTY, str(uuid.uuid4()))


def _publish_ask_ready():
    """Deja constancia de si «Pidemelo» tiene a quien preguntar.

    Sin esto, el skin ofreceria una entrada que siempre contesta «no esta
    configurado», que es ruido en el menu de todo el mundo.
    """
    settings = Addon()
    listo = bool(settings.ai_enabled and settings.ai_base_url)
    ventana = xbmcgui.Window(10000)
    if listo:
        ventana.setProperty(ASK_READY, "1")
    else:
        ventana.clearProperty(ASK_READY)
    return listo


class LibraryMonitor(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.dirty = False

    def onSettingsChanged(self):
        _publish_ask_ready()

    def onScanFinished(self, library):
        if library == "video":
            self.dirty = True

    def onCleanFinished(self, library):
        if library == "video":
            self.dirty = True


def main():
    monitor = LibraryMonitor()
    settings = Addon()
    _publish_session()
    _publish_ask_ready()

    if catalogue.needs_rebuild(settings.rich_index):
        # Arranque en frio: primero la fase barata, para que el recomendador sirva
        # en segundos, y solo despues la cara si esta pedida.
        catalogue.build(rich=False)
        if settings.rich_index:
            catalogue.build(rich=True)

    try:
        while not monitor.abortRequested():
            if monitor.waitForAbort(10):
                break
            if monitor.dirty:
                monitor.dirty = False
                if Addon().rebuild_on_scan:
                    log("la biblioteca cambio: se reconstruye el indice")
                    catalogue.build(rich=Addon().rich_index)
    finally:
        # Si se queda puesta al apagar el complemento, el skin seguiria
        # ofreciendo una entrada que ya no atiende nadie.
        ventana = xbmcgui.Window(10000)
        ventana.clearProperty(ASK_READY)
        ventana.clearProperty(SESSION_PROPERTY)


if __name__ == "__main__":
    main()
