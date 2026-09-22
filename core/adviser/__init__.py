"""Nucleo del recomendador.

No importa `xbmc` en ningun punto: esa es la frontera que permite construir y
evaluar el motor sin Kodi delante. Todo lo que dependa de Kodi vive en la capa
adaptador del addon. Hay una prueba que lo vigila.
"""
