"""Ley del merge interno: `REBASAR_LIBRE` sólo prueba algo si la rama es lineal.

Medido el 26-Nov-2026: de 19 ramas prescritas `REBASAR_LIBRE` en dos sujetos, las 18 con
`rev-list --merges --count base..ref == 0` rebasaron limpias y la única con un merge
interno (`pr/7065`, `psf/requests`) paró en 3 conflictos.

Uso: ley_merge_interno.py REPO TRONCO COBERTURA.tsv
"""
from __future__ import annotations

import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from merge_lattice_governor import repo as R
from merge_lattice_governor.rebase import prescribir
from ley_s6_multisujeto import refs_vivas


def merges(repo: str, base: str, ref: str) -> int:
    return int(
        R.exigir(
            R.git(repo, "rev-list", "--merges", "--count", f"{base}..{ref}"),
            f"rev-list --merges {base}..{ref}",
        ).strip()
    )


def main(argv: list[str]) -> int:
    repo, tronco, cob = argv[1], argv[2], argv[3]
    acto = {f["ref"]: f for f in csv.DictReader(open(cob), delimiter="\t") if f.get("ref")}
    refs = refs_vivas(repo)
    pres = prescribir(repo, tronco, refs)
    print(f"# sujeto {repo} tronco {tronco} · {len(refs)} refs · cobertura {len(acto)} ramas")
    libre = [p for p in pres if p.estado == "REBASAR_LIBRE"]
    filas = []
    for p in libre:
        if p.ref not in acto:
            continue
        base = R.base_de_rama(repo, tronco, p.ref)
        m = merges(repo, base, p.ref)
        filas.append((p.ref, m, acto[p.ref]["paro"], acto[p.ref]["conflictos"]))
    print(f"# REBASAR_LIBRE medidas contra el acto: {len(filas)}")
    for ref, m, paro, con in filas:
        print(f"LIBRE\t{ref}\tmerges={m}\tparo={paro}\tconflictos={con}")
    for etiqueta, filtro in (
        ("lineal (merges=0)", lambda m: m == 0),
        ("con merge interno", lambda m: m > 0),
    ):
        sel = [f for f in filas if filtro(f[1])]
        con = sum(1 for f in sel if f[2] != "0")
        print(f"RESUMEN\t{etiqueta}\tn={len(sel)}\tcon_conflicto={con}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
