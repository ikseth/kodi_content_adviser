"""Motor de similitud. Python puro, sin dependencias.

No es una eleccion de estilo: en el repositorio oficial de complementos de Kodi
**no existen `numpy`, `scipy`, `pandas` ni `scikit-learn`** (comprobado sobre los
1.075 del repositorio de Omega). La libreria no esta donde esto se instala.
"""

from .blend import combine
from .features import FeatureExtractor
from .history import recent_seeds, recommend_from_history
from .index import SimilarityIndex

__all__ = ["FeatureExtractor", "SimilarityIndex", "combine",
           "recent_seeds", "recommend_from_history"]
