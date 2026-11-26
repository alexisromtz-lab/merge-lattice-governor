"""Sonda multi-sujeto de la ley §6: cota estrecha vs cota ancha vs replay del grafo.

Lectura pura sobre el repositorio: sólo `git` de lectura (rev-list, merge-base, diff, log).
El instrumento es el del paquete (`rebase._tocados`), no una reimplementación: si la sonda
midiera con su propio parser, mediría otro objeto.

    estrecha = rutas de `git diff --name-status -M  base..ref`        (diff neto)
    ancha    = rutas de `.. -M --find-copies-harder  base..ref`       (cota ancha, --copias)
    replay   = rutas de `git log --name-only --no-renames base..ref`  (grafo de commits)

La ley que se falsa: `ancha - estrecha` nunca contiene una ruta que el rebase real ponga
en conflicto, y su tamaño es 0 en todo sujeto (la cota ancha no compra cobertura).
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from merge_lattice_governor import repo as R  # noqa: E402
from merge_lattice_governor.rebase import _Clases, _distancias, _tocados  # noqa: E402


def rutas_replay(repo: str, base: str, punta: str) -> set[str]:
    """Rutas que el replay del grafo toca: `log --name-only`, sin detección de renombres.

    Un merge no se despliega sin `-m`: se declara, porque el rebase real corre con
    `--rebase-merges` y ahí sí ve el interior del merge.
    """
    salida = R.exigir(
        R.git(repo, "log", "--name-only", "--no-renames", "--format=", f"{base}..{punta}"),
        f"log --name-only {base}..{punta}",
    )
    return {linea.strip() for linea in salida.splitlines() if linea.strip()}


def refs_vivas(repo: str, patron: str = "refs/remotes/origin/") -> list[str]:
    salida = R.exigir(
        R.git(repo, "for-each-ref", "--format=%(refname:short)", patron),
        f"for-each-ref {patron}",
    )
    return sorted(r for r in salida.split() if not r.endswith("/HEAD"))


def medir(repo: str, tronco: str, refs: list[str]) -> dict:
    filas: list[dict] = []
    for ref in refs:
        atras, adelante = _distancias(repo, tronco, ref)
        if adelante == 0:
            filas.append({"ref": ref, "atras": atras, "adelante": 0, "estado": "SIN_TRABAJO"})
            continue
        base = R.base_de_rama(repo, tronco, ref)
        estrecha = _tocados(repo, base, ref, _Clases())
        ancha = _tocados(repo, base, ref, _Clases(), copias=True)
        replay = rutas_replay(repo, base, ref)
        filas.append(
            {
                "ref": ref,
                "atras": atras,
                "adelante": adelante,
                "estado": "AL_DIA" if atras == 0 else "CON_TRABAJO",
                "|estrecha|": len(estrecha),
                "|ancha|": len(ancha),
                "|replay|": len(replay),
                "solo_ancha": sorted(ancha - estrecha),
                "solo_replay": sorted(replay - estrecha),
            }
        )
    return {"repo": repo, "tronco": tronco, "refs": len(refs), "filas": filas}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("uso: ley_s6_multisujeto.py REPO TRONCO [REF...]", file=sys.stderr)
        return 2
    repo, tronco = argv[1], argv[2]
    refs = argv[3:] or refs_vivas(repo)
    print(json.dumps(medir(repo, tronco, refs), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
