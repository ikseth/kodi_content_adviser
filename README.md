# Recomendador de contenido para Kodi

Complemento para Kodi que recomienda peliculas y series **del catalogo propio**: las
parecidas a la que se esta mirando, y una seleccion en la pantalla principal basada en lo
ultimo que se ha visto.

Se valoran ademas dos funciones: texto predictivo en la busqueda, alimentado por la propia
biblioteca, y enriquecimiento de las recomendaciones con modelos de IA locales o publicos.

## Estado

**En produccion.** El complemento y el clon del skin se instalan y funcionan en Kodi 21
Omega. Lo que hay:

- `addon/plugin.video.content.adviser/` — el complemento: listado de recomendaciones,
  fila en la pantalla de inicio, menu contextual «Similares a esta», buscador predictivo
  y servicio que mantiene el indice al dia.
- `core/adviser/` — el motor. Python puro, sin dependencias, no importa `xbmc`.
- `skin/` — el parche que genera el clon de Estuary, opcional y separable.
- `tools/` — herramientas de desarrollo: construir el indice y evaluarlo.

«Similares a esta» cubre peliculas; para series el indice aun no existe y la interfaz lo
dice en vez de abrir un listado vacio.

## Construir e instalar

```bash
./build_zip.sh                      # el complemento -> dist/
./build_zip.sh --with-ai            # la variante con la capa de IA
./build_skin.sh RUTA_A_SKIN_ESTUARY # el clon del skin, opcional -> dist/
python3 -m pytest tests -q
```

**La variante que se distribuye no lleva la capa de IA**: ni el codigo, ni los
ajustes, ni los textos. La garantia es estructural, no un ajuste que alguien pueda
cambiar. Quien quiera preguntar en lenguaje natural instala la variante `+ai` y
configura su propio servicio.

Los ZIP se instalan en Kodi por «Instalar desde archivo ZIP». El complemento
construye su indice solo, en segundo plano, la primera vez que arranca.

**El clon del skin es opcional y va aparte.** Solo hace falta para la fila en la
pantalla de inicio: Estuary lleva sus widgets escritos a fuego y no admite anadir
uno. Sin el clon se pierde la fila, no el producto. Se genera a partir del Estuary
de la version de Kodi que se vaya a usar, y se regenera al subir de version: no se
mantiene un skin, se mantiene un parche.

Se entrega en dos niveles. **El complemento** funciona en cualquier Kodi con cualquier skin,
lee la biblioteca por JSON-RPC —asi que le da igual que use SQLite o MySQL— y no depende de
ningun servicio externo para funcionar. **Un clon del skin Estuary**, opcional y distribuible
aparte, anade la fila en la pantalla principal y el texto predictivo en el teclado de Kodi;
sin el se pierde la fila, no el producto.

La conexion con modelos de IA es configurable —Ollama, IA_NEST, Claude o cualquier
servicio compatible con OpenAI— y **opcional y apagada por defecto**: el complemento
recomienda igual sin ella.

Cuando se activa, **el modelo no propone titulos**: traduce lo que le pides a un
filtro y es tu catalogo quien contesta. Asi no puede ofrecerte lo que no tienes.

**Antes de escribir codigo conviene leer el apartado 1 del analisis**: parte de esto ya lo
resuelve `TMDb Helper`, que esta en el repositorio oficial de Kodi.

## Licencia

GPL-3.0-or-later.
