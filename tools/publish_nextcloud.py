"""Publica un ZIP en la carpeta de addons de Nextcloud.

Es el camino formal de esta familia de proyectos: los ZIP versionados viven en
`kodi/addons/` del Nextcloud compartido, y **la carpeta es la fuente de verdad, no
un manifiesto**. Un manifiesto hay que mantenerlo, y en cuanto alguien suba un ZIP
sin actualizarlo, miente. La carpeta no puede mentir sobre lo que contiene.

Junto a cada ZIP se publica su `.sha256`, que es lo que el suscriptor comprueba
antes de instalar nada.

**Por defecto no pisa nada.** Un ZIP ya publicado puede estar instalado en media
flota; reemplazarlo con el mismo nombre y distinto contenido deja nodos que creen
tener una cosa y tienen otra. Para eso se sube una version nueva, no se reescribe
la vieja. `--force` existe para el caso en que de verdad haga falta, y lo dice.

La configuracion vive **fuera del repositorio**, porque lleva la contrasena:

    NEXTCLOUD_URL=https://<servidor>/remote.php/dav/files/<usuario>/kodi/addons/
    NEXTCLOUD_USER=<usuario>
    NEXTCLOUD_PASS=<contrasena de aplicacion, revocable por dispositivo>
"""

import argparse
import base64
import hashlib
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_CONFIG = os.path.expanduser("~/kodi-adviser-dev/nextcloud.env")
TIMEOUT = 120

__all__ = ["publish", "listing", "remove", "DEFAULT_CONFIG"]


class PublishError(RuntimeError):
    pass


def _read_config(path):
    settings = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    missing = [k for k in ("NEXTCLOUD_URL", "NEXTCLOUD_USER", "NEXTCLOUD_PASS")
               if not settings.get(k)]
    if missing:
        raise PublishError("faltan claves en %s: %s" % (path, ", ".join(missing)))
    if not settings["NEXTCLOUD_URL"].endswith("/"):
        settings["NEXTCLOUD_URL"] += "/"
    return settings


def _auth_header(settings):
    raw = "%s:%s" % (settings["NEXTCLOUD_USER"], settings["NEXTCLOUD_PASS"])
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _request(settings, method, name="", data=None, extra=None):
    """La contrasena nunca se imprime: los errores se recortan y se sanean."""
    url = settings["NEXTCLOUD_URL"] + name
    headers = {"Authorization": _auth_header(settings)}
    if extra:
        headers.update(extra)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        raise PublishError("no se pudo hablar con el servidor: %s" % error.reason) from None


def listing(settings):
    """Lo que hay publicado ahora mismo, leyendo la carpeta."""
    body = (b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:">'
            b'<d:prop><d:getcontentlength/></d:prop></d:propfind>')
    status, payload = _request(settings, "PROPFIND", data=body,
                               extra={"Depth": "1", "Content-Type": "application/xml"})
    if status not in (207, 200):
        raise PublishError("la carpeta no se pudo listar (HTTP %s)" % status)
    text = payload.decode("utf-8", "replace")
    names = []
    for href in re.findall(r"<d:href>([^<]+)</d:href>", text, re.IGNORECASE):
        name = urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])
        if name.endswith((".zip", ".sha256")):
            names.append(name)
    return sorted(names)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _upload(settings, path, name, force, dry_run):
    existing = listing(settings)
    if name in existing and not force:
        raise PublishError(
            "%s ya esta publicado. Un ZIP publicado puede estar instalado en media "
            "flota: para cambiarlo se sube una version nueva, no se reescribe la "
            "vieja. Si de verdad hace falta, --force." % name)
    if dry_run:
        return "se subiria %s (%d KB)" % (name, os.path.getsize(path) // 1024)
    with open(path, "rb") as handle:
        data = handle.read()
    status, _ = _request(settings, "PUT", name, data=data,
                         extra={"Content-Type": "application/zip"})
    if status not in (200, 201, 204):
        raise PublishError("fallo al subir %s (HTTP %s)" % (name, status))
    return "subido %s (%d KB)" % (name, len(data) // 1024)


def publish(settings, zip_path, force=False, dry_run=False):
    """Sube el ZIP y su `.sha256`, y comprueba que quedan los dos."""
    name = os.path.basename(zip_path)
    digest = _sha256(zip_path)
    lines = [_upload(settings, zip_path, name, force, dry_run)]

    checksum_name = name + ".sha256"
    content = ("%s  %s\n" % (digest, name)).encode()
    if checksum_name in listing(settings) and not force and not dry_run:
        raise PublishError("%s ya esta publicado" % checksum_name)
    if dry_run:
        lines.append("se subiria %s" % checksum_name)
    else:
        status, _ = _request(settings, "PUT", checksum_name, data=content,
                             extra={"Content-Type": "text/plain"})
        if status not in (200, 201, 204):
            raise PublishError("fallo al subir %s (HTTP %s)" % (checksum_name, status))
        lines.append("subido %s" % checksum_name)

    if not dry_run:
        publicados = listing(settings)
        for esperado in (name, checksum_name):
            if esperado not in publicados:
                raise PublishError("%s no aparece en la carpeta tras subirlo" % esperado)
        # Que aparezca en el listado no prueba que este intacto: una subida
        # truncada tambien aparece. Se baja y se contrasta el hash, que es lo
        # que hara el nodo antes de instalarlo.
        status, bajado = _request(settings, "GET", name)
        if status != 200:
            raise PublishError("no se pudo releer %s (HTTP %s)" % (name, status))
        if hashlib.sha256(bajado).hexdigest() != digest:
            raise PublishError(
                "%s llego corrupto: el hash de lo publicado no coincide con el "
                "del fichero local. NO instalarlo." % name)
        lines.append("comprobado: descargado de vuelta y el sha256 coincide")
    lines.append("sha256 %s" % digest)
    return lines


def remove(settings, name):
    """Retira un fichero publicado. **Solo para una version rota.**

    Borrar de la carpeta compartida no es una operacion de rutina: quien ya la
    tenga instalada se queda como esta, y quien no, deja de poder instalarla.
    Para cambiar algo se sube una version nueva. Esto existe para lo otro: un ZIP
    que se sabe defectuoso y que nadie deberia instalar.
    """
    publicados = listing(settings)
    if name not in publicados:
        raise PublishError("%s no esta publicado" % name)
    retirados = []
    for objetivo in (name, name + ".sha256"):
        if objetivo not in publicados:
            continue
        status, _ = _request(settings, "DELETE", objetivo)
        if status not in (200, 204):
            raise PublishError("fallo al retirar %s (HTTP %s)" % (objetivo, status))
        retirados.append(objetivo)
    quedan = listing(settings)
    for objetivo in retirados:
        if objetivo in quedan:
            raise PublishError("%s sigue en la carpeta tras retirarlo" % objetivo)
    return retirados


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("zips", nargs="*", help="ZIP(s) a publicar")
    parser.add_argument("--config", help="fichero con las credenciales")
    parser.add_argument("--list", action="store_true", help="solo listar lo publicado")
    parser.add_argument("--dry-run", action="store_true",
                        help="dice lo que haria, sin subir nada")
    parser.add_argument("--force", action="store_true",
                        help="reemplaza un nombre ya publicado")
    parser.add_argument("--remove", metavar="NOMBRE",
                        help="retira un ZIP publicado y su .sha256. Solo para una "
                             "version rota: lo normal es subir una version nueva")
    args = parser.parse_args(argv)

    try:
        settings = _read_config(args.config or DEFAULT_CONFIG)
    except (OSError, PublishError) as error:
        print("No se pudo leer la configuracion: %s" % error, file=sys.stderr)
        print("Se esperaba un fichero como %s con NEXTCLOUD_URL, NEXTCLOUD_USER "
              "y NEXTCLOUD_PASS." % DEFAULT_CONFIG, file=sys.stderr)
        return 2

    try:
        if args.remove:
            for nombre in remove(settings, args.remove):
                print("retirado %s" % nombre)
            return 0
        if args.list or not args.zips:
            for name in listing(settings):
                print(name)
            return 0
        for zip_path in args.zips:
            if not os.path.isfile(zip_path):
                print("no existe: %s" % zip_path, file=sys.stderr)
                return 2
            for line in publish(settings, zip_path, args.force, args.dry_run):
                print(line)
    except PublishError as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
