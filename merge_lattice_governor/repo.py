"""Lectores de git. Todo por subprocess: el paquete no tiene dependencias."""

from __future__ import annotations

import re
import subprocess

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


_CABECERA = re.compile(r"^  (base|our|their)\s+([0-9]+)\s+([0-9a-f]{40})\s+(.*)$")


def rutas_en_conflicto(repo: str, base: str, a: str, b: str) -> tuple[str, ...]:
    """Rutas que dejan marcas al fusionar ``a`` y ``b``.

    ``git merge-tree`` (forma de tres argumentos) devuelve RC 0 siempre y escribe
    ``changed in both`` también en los merges limpios: el único discriminante
    son las marcas ``<<<<<<< .our``. Esa forma no escribe objetos en el ODB.
    """
    proceso = git(repo, "merge-tree", base, a, b)
    exigir(proceso, f"merge-tree {a} {b}")
    tocadas: set[str] = set()
    actual: str | None = None
    for linea in proceso.stdout.splitlines():
        cabecera = _CABECERA.match(linea)
        if cabecera:
            actual = cabecera.group(4).strip()
            continue
        if "<<<<<<< .our" in linea and actual:
            tocadas.add(actual)
    return tuple(sorted(tocadas))
