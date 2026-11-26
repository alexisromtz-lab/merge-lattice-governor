"""Cobertura de la cota estrecha contra el acto real, rama a rama.

Para cada rama: rebase real en un clon desechable, se registran las rutas del **primer paro**
y se cuenta cuántas estaban en la cota estrecha (diff neto) y en la cota ancha (--find-copies-harder).

    cobertura.py REPO TRONCO RAMA...

Publica TSV: ref · atrás · |estrecha| · |ancha| · conflictos · cubiertas · solo_ancha · no_cubiertas
"""

from __future__ import annotations
import pathlib

import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from merge_lattice_governor import repo as R  # noqa: E402
from merge_lattice_governor.rebase import _Clases, _distancias, _tocados  # noqa: E402


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, "-c", "rerere.enabled=false", *args],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_EDITOR": "true",
            "GIT_SEQUENCE_EDITOR": "true",
            "HOME": "/Users/marlene",
        },
    )


def primer_paro(repo: str, tronco: str, ref: str) -> tuple[bool, list[str]]:
    """Rebase real hasta el primer conflicto. Devuelve ``(en_conflicto, rutas)``."""
    _git(repo, "checkout", "-q", "--detach", ref)
    proc = _git(repo, "rebase", "--rebase-merges", tronco)
    rutas = _git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()
    en_conflicto = proc.returncode != 0
    _git(repo, "rebase", "--abort")
    _git(repo, "checkout", "-q", "--detach", tronco)
    return en_conflicto, rutas


def main(argv: list[str]) -> int:
    repo, tronco, refs = argv[1], argv[2], argv[3:]
    print("ref\tatras\testrecha\tancha\tparo\tconflictos\tcubiertas\tsolo_ancha\tno_cubiertas")
    for ref in refs:
        atras, adelante = _distancias(repo, tronco, ref)
        if adelante == 0:
            continue
        base = R.base_de_rama(repo, tronco, ref)
        est = _tocados(repo, base, ref, _Clases())
        anh = _tocados(repo, base, ref, _Clases(), copias=True)
        paro, conflicto = primer_paro(repo, tronco, ref)
        cubiertas = [p for p in conflicto if p in est]
        no_cubiertas = [p for p in conflicto if p not in est]
        print(
            f"{ref}\t{atras}\t{len(est)}\t{len(anh)}\t{int(paro)}\t{len(conflicto)}\t"
            f"{len(cubiertas)}\t{len(anh - est)}\t{','.join(no_cubiertas)}"
        )
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
