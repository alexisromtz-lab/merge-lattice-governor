"""Cruce de la sonda (cota) con el acto real (primer paro del rebase).

    censo.txt  · JSON de ley_s6_multisujeto.py
    cob.tsv    · TSV de cobertura.py
    veredictos · JSON {ref: {estado, atras}}

Publica la matriz de confusión del veredicto contra el acto y la cobertura de cada cota.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from merge_lattice_governor.rebase import prescribir  # noqa: E402


def cargar_cob(ruta: str) -> dict[str, dict]:
    filas = {}
    for f in csv.DictReader(open(ruta), delimiter="\t"):
        if not f.get("ref"):
            continue
        filas[f["ref"]] = {
            "atras": int(f["atras"]),
            "estrecha": int(f["estrecha"]),
            "ancha": int(f["ancha"]),
            "paro": int(f["paro"]),
            "conflictos": int(f["conflictos"]),
            "cubiertas": int(f["cubiertas"]),
            "solo_ancha": int(f["solo_ancha"]),
            "no_cubiertas": [p for p in (f["no_cubiertas"] or "").split(",") if p],
        }
    return filas


def main(argv: list[str]) -> int:
    sujeto, repo, censo, cob = argv[1], argv[2], argv[3], argv[4]
    refs = [f["ref"] for f in json.load(open(censo))["filas"] if f["estado"] != "SIN_TRABAJO"]
    acto = cargar_cob(cob)
    veredictos = {p.ref: p.estado for p in prescribir(repo, "origin/main", refs)}
    confusion: Counter[tuple[str, str]] = Counter()
    sin_acto = [r for r in refs if r not in acto]
    for ref in refs:
        if ref in acto:
            confusion[(veredictos[ref], "conflicto" if acto[ref]["paro"] else "limpio")] += 1
    total_conf = sum(a["conflictos"] for a in acto.values())
    cubiertas = sum(a["cubiertas"] for a in acto.values())
    print(f"=== {sujeto} ({len(refs)} ramas con trabajo) ===")
    print(f"  veredictos: {dict(Counter(veredictos.values()))}")
    print(f"  sin medida de acto: {len(sin_acto)}")
    for (estado, acto_), n in sorted(confusion.items()):
        print(f"  {estado:<20} → {acto_:<10} {n}")
    print(f"  rutas en conflicto {total_conf} · cubiertas {cubiertas} · cobertura "
          f"{0 if not total_conf else 100 * cubiertas / total_conf:.1f}%")
    solo_ancha = sum(a["solo_ancha"] for a in acto.values())
    print(f"  rutas solo-ancha {solo_ancha}")
    por_regimen: dict[str, list[dict]] = defaultdict(list)
    for a in acto.values():
        clave = "0-10" if a["atras"] <= 10 else "11-50" if a["atras"] <= 50 else "51-150" if a["atras"] <= 150 else "151+"
        por_regimen[clave].append(a)
    for clave in ("0-10", "11-50", "51-150", "151+"):
        g = por_regimen.get(clave, [])
        if not g:
            continue
        t = sum(a["conflictos"] for a in g)
        c = sum(a["cubiertas"] for a in g)
        print(f"  atrás {clave:>7}: ramas {len(g):>3} · con conflicto {sum(a['paro'] for a in g):>3} · rutas {t:>4} · cobertura {0 if not t else 100 * c / t:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
