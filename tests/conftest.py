import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for ruta in (os.path.join(RAIZ, "core"), os.path.join(RAIZ, "tools")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
