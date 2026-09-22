"""Lectura de la videoteca de Kodi."""

from .reader import (
    BASIC_MOVIE_FIELDS,
    BASIC_TVSHOW_FIELDS,
    RICH_MOVIE_FIELDS,
    RICH_TVSHOW_FIELDS,
    LibraryReader,
)

__all__ = ["LibraryReader", "BASIC_MOVIE_FIELDS", "RICH_MOVIE_FIELDS",
           "BASIC_TVSHOW_FIELDS", "RICH_TVSHOW_FIELDS"]
