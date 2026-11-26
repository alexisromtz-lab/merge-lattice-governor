"""Censo §6 + cardinal de merges internos por rama (lectura pura).

`merges` es el número de commits de merge en `base..ref`: el único dato que el
instrumento no mira hoy y que decide si el replay re-ejecuta un merge del tronco.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from merge_lattice_governor import repo as R
from ley_s6_multisujeto import medir, refs_vivas


def enriquecer(repo: str, tronco: str, refs: list[str]) -> dict:
    censo = medir(repo, tronco, refs)
    for fila in censo["filas"]:
        if fila["estado"] == "SIN_TRABAJO":
            fila["merges"] = 0
            continue
        base = R.base_de_rama(repo, tronco, fila["ref"])
        fila["merges"] = int(
            R.exigir(
                R.git(repo, "rev-list", "--merges", "--count", f"{base}..{fila['ref']}"),
                f"rev-list --merges {base}..{fila['ref']}",
            ).strip()
        )
    return censo


def main(argv: list[str]) -> int:
    repo, tronco = argv[1], argv[2]
    refs = argv[3:] or refs_vivas(repo)
    print(json.dumps(enriquecer(repo, tronco, refs), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
