"""Capa de IA: **el modelo traduce, el catalogo decide**.

Es la regla que gobierna todo lo de aqui, y no es una precaucion generica. Un
modelo al que se le pide «recomiendame algo» contesta con peliculas que no
tienes: ha leido internet, no tu disco duro. Recomendar lo que no se puede poner
es peor que no recomendar.

Asi que el modelo **no nombra obras**. Recibe una frase en lenguaje natural y
devuelve una consulta estructurada —generos, decada, duracion, personas— que
luego se aplica contra la biblioteca real. Todo lo que el modelo puede decir es
comprobable, y lo que no encaja se descarta antes de llegar a la pantalla.

Corolario: **sin servicio de IA todo lo demas sigue igual**. Esto es una entrada
mas al catalogo, no una pieza del camino critico.
"""

from .filters import to_library_filter, to_sort
from .providers import (
    ANTHROPIC,
    IA_NEST,
    OPENAI_COMPATIBLE,
    build_request,
    parse_response,
)
from .query import Query, build_prompt, parse_query

__all__ = ["OPENAI_COMPATIBLE", "ANTHROPIC", "IA_NEST", "build_request", "parse_response",
           "Query", "build_prompt", "parse_query", "to_library_filter", "to_sort"]
