"""Lectores de git. Todo por subprocess: el paquete no tiene dependencias."""

from __future__ import annotations

import atexit
import fnmatch
import os
import posixpath
import shutil
import subprocess
import tempfile

from .ley import Masa, clase_de


class ErrorGit(Exception):
    """Referencia, ruta o repositorio ilegible. El CLI lo traduce a RC 2."""


def git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, errors="replace", check=False
    )


def exigir(proceso: subprocess.CompletedProcess, que: str) -> str:
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout).strip().splitlines()
        cola = f" · {detalle[0]}" if detalle else ""
        raise ErrorGit(f"{que}: RC {proceso.returncode}{cola}")
    return proceso.stdout


def resolver(repo: str, ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise ErrorGit(f"referencia no legible: {ref!r}")
    proceso = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proceso.returncode != 0:
        raise ErrorGit(f"referencia no legible: {ref}")
    return proceso.stdout.strip()


def es_repo(repo: str) -> bool:
    return git(repo, "rev-parse", "--git-dir").returncode == 0


def base_de_par(repo: str, a: str, b: str) -> str | None:
    proceso = git(repo, "merge-base", a, b)
    if proceso.returncode != 0:
        return None
    return proceso.stdout.strip() or None


def base_de_rama(repo: str, tronco: str, ref: str) -> str:
    """La base de una rama no es el tronco: es su merge-base con él."""
    return base_de_par(repo, tronco, ref) or tronco


def rutas(repo: str, base: str, ref: str) -> list[str]:
    salida = exigir(git(repo, "diff", "--name-only", "--no-renames", base, ref), f"diff {base}..{ref}")
    return [linea for linea in salida.splitlines() if linea]


def leer(repo: str, ref: str, ruta: str) -> str | None:
    proceso = git(repo, "show", f"{ref}:{ruta}")
    return proceso.stdout if proceso.returncode == 0 else None


def masa(repo: str, base: str, ref: str) -> Masa:
    """Suma algebraica de líneas de código, clasificada por su ruta."""
    salida = exigir(
        git(repo, "diff", "--numstat", "--no-renames", base, ref), f"numstat {base}..{ref}"
    )
    total = Masa()
    for linea in salida.splitlines():
        campos = linea.split("\t")
        if len(campos) < 3:
            continue
        sumadas, borradas, ruta = campos[0], campos[1], campos[2]
        clase = clase_de(ruta)
        if clase is None or sumadas == "-" or borradas == "-":
            continue
        total = total.sumar(clase, int(sumadas) - int(borradas))
    return total


_ORACULOS: dict[str, str] = {}


def _odm(repo: str) -> str:
    """Ruta absoluta del ODB del sujeto: lo que el oráculo va a montar en alternates."""
    ruta = exigir(
        git(repo, "rev-parse", "--path-format=absolute", "--git-path", "objects"),
        f"ODB de {repo}",
    ).strip()
    if not ruta or not os.path.isdir(ruta):
        raise ErrorGit(f"ODB ilegible en {repo}")
    return ruta


def _oraculo(repo: str) -> str:
    """Repositorio de usar y tirar cuyo ODB **es** el del sujeto, por `alternates`.

    El merge se ejecuta aquí y sus árboles aterrizan en este ODB vacío: el sujeto
    no recibe una sola escritura. Bare no sirve — `safe.bareRepository = explicit`
    lo bloquea en las versiones de git que traen ese default.
    """
    odm = _odm(repo)
    raiz = _ORACULOS.get(odm)
    if raiz is not None and os.path.isdir(raiz):
        return raiz
    raiz = tempfile.mkdtemp(prefix="mlg-oraculo-")
    exigir(subprocess.run(
        ["git", "init", "-q", raiz], capture_output=True, text=True, errors="replace", check=False
    ), f"git init {raiz}")
    info = os.path.join(raiz, ".git", "objects", "info")
    os.makedirs(info, exist_ok=True)
    with open(os.path.join(info, "alternates"), "w", encoding="utf-8") as fichas:
        fichas.write(odm + "\n")
    atexit.register(shutil.rmtree, raiz, True)
    _ORACULOS[odm] = raiz
    return raiz


def _es_superficial(repo: str) -> bool:
    """``True`` si el clon no tiene historia: la base de la pareja puede faltar."""
    proc = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _causa_merge_tree(
    proc: subprocess.CompletedProcess, a: str, b: str, repo: str | None = None
) -> str:
    """RC que no es 0 ni 1: nombra la causa, no el síntoma.

    Medido el 26-Nov-2026, dos clones distintos y dos causas distintas detrás del
    mismo RC 128: en un clon ``--filter=blob:none`` el mensaje es ``unable to read
    blob object …``; en un clon ``--depth 1`` es ``Could not read <oid>`` y el
    remedio es ``git fetch --unshallow``. Un solo texto para las dos mandaba al
    operador a arreglar lo que no estaba roto (medido el 27-Nov-2026 en el
    cold-clone de la propia v0.5.0, que se diagnosticó como «clon parcial»).
    """
    linea = (proc.stderr or proc.stdout).strip().splitlines()
    cola = f" · {linea[0]}" if linea else ""
    baja = cola.lower()
    if "unable to read blob" in baja or "promisor" in baja:
        causa = (
            "clon parcial: el predicado exacto lee blobs que el filtro no trajo;"
            " remedio: clonar sin --filter (medido: `git fetch --refetch` repuebla"
            " casi todo y aun así dejó un blob pendiente)"
        )
    elif "could not read" in baja or (repo is not None and _es_superficial(repo)):
        causa = (
            "clon superficial: la base de la pareja no está en el clon y sin ella no"
            " hay tres bandas; remedio: `git fetch --unshallow`"
        )
    else:
        causa = "sin --write-tree este git no puede distinguir un conflicto de driver"
    return f"merge-tree --write-tree {a} {b}: RC {proc.returncode}{cola} · {causa}"


def rutas_en_conflicto(repo: str, a: str, b: str) -> tuple[str, ...]:
    """Rutas que un merge a tres bandas deja **en conflicto**: lo dice el merge.

    ``merge-tree --write-tree`` (dos argumentos) calcula él mismo la base —la de
    la pareja— y devuelve RC 1 con la lista de rutas. La forma de tres argumentos
    sólo imprime ``<<<<<<< .our`` para los conflictos de **contenido**: una ruta
    gobernada por ``merge=<nombre>`` en ``.gitattributes`` se resuelve —o se
    aborta— dentro del driver, sin marcas, y el par se leía limpio (medido: 13 de
    105 parejas del corpus). Sin ``--write-tree`` no hay medida: RC 2, nunca
    degradar al parser de marcas.

    Límite declarado: el oráculo no tiene árbol de trabajo, así que no aplica los
    drivers del sujeto. Su veredicto es el del **merge genérico**; qué rutas
    decide un driver lo publica ``drivers()``, y esas rutas viajan aparte.
    """
    oid_a, oid_b = resolver(repo, a), resolver(repo, b)
    proc = subprocess.run(
        ["git", "-C", _oraculo(repo), "-c", "core.quotepath=false",
         "merge-tree", "--write-tree", "--name-only", str(oid_a), str(oid_b)],
        capture_output=True, text=True, errors="replace", check=False,
    )
    if proc.returncode not in (0, 1):
        raise ErrorGit(_causa_merge_tree(proc, a, b, repo))
    cabecera = proc.stdout.split("\n\n", 1)[0].splitlines()
    rutas = tuple(sorted(linea.strip() for linea in cabecera[1:] if linea.strip()))
    if proc.returncode == 1 and not rutas:
        # RC 1 con stdout vacío no es «conflicto sin rutas»: es un merge que no corrió
        # (referencia ausente en el oráculo). Leerlo como limpio es el falso verde.
        linea = (proc.stderr or proc.stdout).strip().splitlines()
        cola = f" · {linea[0]}" if linea else ""
        raise ErrorGit(f"merge-tree {a} {b}: RC 1 sin rutas ni árbol{cola}")
    return rutas


def drivers(repo: str, refs: list[str]) -> dict[str, str]:
    """``patrón → driver`` de ``merge=<nombre>`` declarado en el ``.gitattributes`` de ``refs``.

    Es lo que el oráculo **no** aplica: publicarlo convierte una aproximación
    silenciosa en un límite declarado.
    """
    reglas: dict[str, str] = {}
    for ref in refs:
        texto = leer(repo, ref, ".gitattributes")
        if texto is None:
            continue
        for linea in texto.splitlines():
            limpia = linea.split("#", 1)[0].strip()
            if not limpia:
                continue
            campos = limpia.split()
            for campo in campos[1:]:
                if campo.startswith("merge=") and len(campo) > 6:
                    reglas[campos[0]] = campo[6:]
    return reglas


def driver_de(reglas: dict[str, str], ruta: str) -> str | None:
    """Última regla que casa, como git: patrón con ``/`` contra la ruta, sin él contra el nombre."""
    encontrado: str | None = None
    base = posixpath.basename(ruta)
    for patron, nombre in reglas.items():
        objetivo = ruta if "/" in patron else base
        if fnmatch.fnmatchcase(objetivo, patron):
            encontrado = nombre
    return encontrado
