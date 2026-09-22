"""Construir la pregunta a golpe de mando, sin teclearla.

**El problema no es la IA: es el teclado.** Con teclado fisico o dictado por voz,
preguntar en lenguaje natural es comodo. Con un mando sobre una cuadricula de
letras, escribir «algo corto y de risa para esta noche» cuesta tanto que nadie lo
hara dos veces. La funcionalidad se cae sola, no por mala sino por inalcanzable.

**Por que no un diccionario general de castellano.** La idea de los teclados de
movil —predecir la siguiente palabra— es la correcta, pero un corpus general
tiene dos problemas aqui: pesa, y **sugiere palabras que el sistema no sabe
contestar**. «Algo de...» seguido de mil continuaciones posibles, de las que solo
unas pocas llevan a una pelicula de tu casa.

Asi que el diccionario es **del dominio y del catalogo**: unas pocas decenas de
fragmentos, cada uno anclado en algo que el filtro sabe expresar y que **existe de
verdad en tu biblioteca**. No se ofrece «de los cincuenta» si no tienes ninguna de
los cincuenta, ni «de Kurosawa» si no tienes ninguna suya. Toda sugerencia lleva a
algun sitio.

Y sigue siendo lenguaje natural: lo que se compone se le pasa al modelo igual, asi
que una combinacion que no previmos aqui tambien funciona.
"""

__all__ = ["PhraseBook", "Fragment", "GENRE", "DURATION", "ERA", "PERSON",
           "SORT", "CONNECTOR"]

GENRE = "genre"
DURATION = "duration"
ERA = "era"
PERSON = "person"
SORT = "sort"

# El orden en que se ofrecen las ranuras cuando la frase esta vacia o a medias.
# Primero lo que mas acota y mas sabe decir la gente.
CONNECTOR = "connector"

SLOT_ORDER = (GENRE, CONNECTOR, DURATION, ERA, PERSON, SORT)

# Como arranca una frase. Se ofrece solo con la caja vacia.
#
# **No dice si es pelicula o serie a proposito.** El sistema ya lo sabe por donde
# se ha pulsado, asi que hacerselo teclear al usuario es cobrarle una pulsacion
# por una informacion que ya se tiene.
OPENERS = ("algo",)

# Para encadenar generos. **«y» y «o» no significan lo mismo**: uno exige los dos
# generos y el otro se conforma con cualquiera, y el filtro los distingue.
CONNECTORS = ("y", "o")

# Frase coloquial -> genero que tiene que existir en el catalogo para ofrecerla.
# La traduccion de verdad la hace el modelo; esto solo evita ofrecer lo que no
# se tiene.
GENRE_PHRASES = (
    ("de risa", "Comedia"),
    ("de miedo", "Terror"),
    ("de accion", "Accion"),
    ("de suspense", "Suspense"),
    ("de ciencia ficcion", "Ciencia ficcion"),
    ("de aventuras", "Aventura"),
    ("de animacion", "Animacion"),
    ("para toda la familia", "Familia"),
    ("de drama", "Drama"),
    ("de crimen", "Crimen"),
    ("del oeste", "Western"),
    ("de guerra", "Belica"),
    ("de documentales", "Documental"),
    ("de romance", "Romance"),
    ("de fantasia", "Fantasia"),
    ("de historia", "Historia"),
)

# Todas las frases tienen que encajar detras de cualquier arranque: «algo de
# risa» y «una peli de risa» valen igual. Por eso nada de adjetivos con genero
# —«algo corta» no es castellano— y se prefiere «que dure poco».
DURATION_PHRASES = ("que dure poco", "que dure menos de 90 minutos",
                    "que dure menos de dos horas")
SORT_PHRASES = ("de las mejor valoradas", "al azar")


def _fold(text):
    """Comparacion tolerante: minusculas y sin tildes. Igual que el buscador,
    y por el mismo motivo: el mando."""
    import unicodedata
    text = " ".join(str(text or "").split()).lower()
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))


class Fragment:
    def __init__(self, text, slot):
        self.text = text
        self.slot = slot

    def __repr__(self):  # pragma: no cover - solo para depurar
        return "Fragment(%r, %r)" % (self.text, self.slot)

    def __eq__(self, other):
        return (isinstance(other, Fragment) and self.text == other.text
                and self.slot == other.slot)


class PhraseBook:
    """Los fragmentos que este catalogo concreto puede ofrecer."""

    def __init__(self, fragments, media_type="movie", genre_names=()):
        self._fragments = list(fragments)
        self.media_type = media_type
        # **Tambien el nombre real del genero, no solo la frase que ofrecemos.**
        # Ofrecemos «de miedo» pero alguien puede teclear «de terror», y sin esto
        # se le seguian ofreciendo mas generos: «algo de terror de risa».
        self._genre_names = tuple(_fold(g) for g in genre_names if g)

    @property
    def size(self):
        return len(self._fragments)

    @classmethod
    def build(cls, genres=(), people=(), decades=(), media_type="movie"):
        """`genres` son los que existen; `decades` y `people`, ya ordenados por
        presencia en el catalogo, que es el orden en que se ofreceran."""
        fragments = []

        # En el orden en que llegan los generos, que quien construye el material
        # los ordena por cuantas obras tiene de cada uno.
        frase_de = {_fold(g): p for p, g in GENRE_PHRASES}
        for genre in genres:
            phrase = frase_de.get(_fold(genre))
            if phrase:
                fragments.append(Fragment(phrase, GENRE))

        for connector in CONNECTORS:
            fragments.append(Fragment(connector, CONNECTOR))

        # La duracion es de la pelicula. Una serie no tiene una: la tiene cada
        # episodio, asi que preguntar por ella no lleva a ningun sitio.
        if media_type == "movie":
            for phrase in DURATION_PHRASES:
                fragments.append(Fragment(phrase, DURATION))

        # **En el orden en que llegan**, que quien construye el material las
        # ordena por cuantas peliculas tiene de cada una. Por orden cronologico,
        # lo primero que se ofrece son los anos veinte, que en casi cualquier
        # catalogo son cuatro peliculas.
        for decade in decades:
            fragments.append(Fragment("de los %s" % _decade_name(decade), ERA))

        for name in people:
            fragments.append(Fragment("de %s" % name, PERSON))

        for phrase in SORT_PHRASES:
            fragments.append(Fragment(phrase, SORT))

        return cls(fragments, media_type, genres)

    def _used_slots(self, folded_text):
        used = set()
        for fragment in self._fragments:
            if fragment.slot == CONNECTOR:
                continue  # un conector suelto no agota nada
            if _fold(fragment.text) in folded_text:
                used.add(fragment.slot)
        for nombre in self._genre_names:
            if nombre in folded_text:
                used.add(GENRE)
        return used

    def suggest(self, text, limit=9, history=()):
        """Devuelve `[(frase_completa, etiqueta)]`.

        La frase completa es lo que quedara en la caja al elegir; la etiqueta, lo
        que se lee en la lista. Son la misma cosa a proposito: ver lo que vas a
        obtener evita la sorpresa de que el texto cambie de otra forma.
        """
        raw = " ".join(str(text or "").split())
        folded = _fold(raw)

        # Lo primero, lo ya preguntado: a partir del tercer uso es lo que mas se
        # repite, y no cuesta nada.
        results = []
        for question in history:
            if folded and folded not in _fold(question):
                continue
            if question not in [r[0] for r in results]:
                results.append((question, question))
            if limit and len(results) >= limit:
                return results

        if not raw:
            for opener in OPENERS:
                results.append((opener, opener))
                if limit and len(results) >= limit:
                    return results

        used = self._used_slots(folded)
        words = raw.split()

        # Tras un «y» o un «o» toca decir con que se encadena, asi que los
        # generos vuelven a ofrecerse aunque ya hubiera uno: es justo lo que se
        # estaba pidiendo al pulsar el conector.
        if words and _fold(words[-1]) in CONNECTORS:
            encadenables = []
            for fragment in self._fragments:
                if fragment.slot != GENRE or _fold(fragment.text) in folded:
                    continue
                encadenables.append(("%s %s" % (raw, fragment.text), fragment.text))
                if limit and len(results) + len(encadenables) >= limit:
                    break
            return (results + encadenables)[:limit] if limit else results + encadenables

        # Un conector sin nada que encadenar no lleva a ningun sitio.
        if GENRE not in used:
            used.add(CONNECTOR)

        # Dos clases de sugerencia, y **no se mezclan**: si algo de lo escrito es
        # el principio de un fragmento, el usuario esta a medias de escribirlo y
        # solo tiene sentido completarlo. Anadir detras daria «algo de r de
        # miedo», que no es una frase.
        completions, appends = [], []
        for slot in SLOT_ORDER:
            if slot in used:
                continue
            for fragment in self._fragments:
                if fragment.slot != slot:
                    continue
                completed, overlapped = self._complete(words, raw, fragment)
                if completed is None or completed == raw:
                    continue
                (completions if overlapped else appends).append(
                    (completed, fragment.text))

        for completed, label in (completions or appends):
            if completed in [r[0] for r in results]:
                continue
            results.append((completed, label))
            if limit and len(results) >= limit:
                break
        return results

    @staticmethod
    def _complete(words, raw, fragment):
        """Encaja el fragmento con el final de lo tecleado.

        Se prueba el solape **mas largo primero**: con «algo de r» y el fragmento
        «de risa», lo que ya esta escrito es «de r», no solo la «r». Comparar solo
        la ultima palabra no encuentra nada, que es justo lo que fallaba.

        Devuelve `(frase, hubo_solape)`. Sin solape la frase se anade detras, y
        quien llama decide si eso vale: asi «algo» —que no empieza ningun
        fragmento— sigue ofreciendo continuaciones en vez de quedarse en blanco.
        """
        folded_fragment = _fold(fragment.text)
        for taken in range(len(words), 0, -1):
            tail = " ".join(words[len(words) - taken:])
            folded_tail = _fold(tail)
            if folded_fragment == folded_tail:
                return None, True  # ya esta escrito entero
            if folded_fragment.startswith(folded_tail):
                head = " ".join(words[:len(words) - taken])
                return ("%s %s" % (head, fragment.text)).strip(), True
        return ("%s %s" % (raw, fragment.text)).strip(), False


# El siglo importa: **`1920` no es «dos mil veinte»**. Mirar solo las dos ultimas
# cifras ofrecia «de los dos mil veinte» para las peliculas de 1920, que es una
# forma segura de no encontrar nada.
_1900S = {0: "mil novecientos", 10: "diez", 20: "veinte", 30: "treinta",
          40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta",
          80: "ochenta", 90: "noventa"}
_2000S = {0: "dos mil", 10: "dos mil diez", 20: "dos mil veinte",
          30: "dos mil treinta", 40: "dos mil cuarenta"}


def _decade_name(decade):
    """`1980` -> `ochenta`, `2020` -> `dos mil veinte`. En castellano se dicen
    asi, no «de los 1980»."""
    value = int(decade)
    tens = value % 100
    table = _2000S if value >= 2000 else _1900S
    return table.get(tens, str(value))
