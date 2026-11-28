#!/usr/bin/env python3
"""Tabla de la escalera a partir de los TSV de ``escalera.py``.

Lee uno o más ``parejas_*.tsv`` (columnas ``a``, ``b``, ``k``, ``veredicto``) y
publica, por terreno, la densidad de conflicto y la probabilidad de conflicto en
cada tramo de ``k``, con intervalo de Wilson al 95 %. Sólo lee: cero llamadas a
``git``, cero escrituras.

Uso:

    python3 resumen.py parejas_typer.tsv parejas_httpx.tsv
"""

from __future__ import annotations

import math
import sys

CONFLICTO = "CONFLICTO_TEXTUAL"


def wilson(exitos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = exitos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    radio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centro - radio), min(1.0, centro + radio))


def tramos(k: int) -> str:
    return "k=0" if k == 0 else ("k=1" if k == 1 else "k>=2")


def main(argv: list[str]) -> int:
    if not argv:
        print("uso: resumen.py parejas_*.tsv [...]", file=sys.stderr)
        return 2
    print("terreno\tn\tconflictos\tdensidad\ttramo\tn_tramo\tconf\ttasa\tIC95")
    for ruta in argv:
        cuentas = {"k=0": [0, 0], "k=1": [0, 0], "k>=2": [0, 0]}
        total = rojas = 0
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                campos = linea.rstrip("\n").split("\t")
                if len(campos) < 4 or not campos[2].lstrip("-").isdigit():
                    continue
                k = int(campos[2])
                es_conflicto = campos[3] == CONFLICTO
                t = tramos(k)
                cuentas[t][0] += 1
                cuentas[t][1] += int(es_conflicto)
                total += 1
                rojas += int(es_conflicto)
        nombre = ruta.rsplit("/", 1)[-1].removesuffix(".tsv")
        lo, hi = wilson(rojas, total)
        print(f"{nombre}\t{total}\t{rojas}\t{rojas / total:.4f}\tTOTAL\t{total}\t{rojas}\t{rojas / total:.4f}\t[{lo:.4f};{hi:.4f}]")
        for t, (n, c) in cuentas.items():
            lo, hi = wilson(c, n)
            print(f"{nombre}\t{total}\t{rojas}\t{rojas / total:.4f}\t{t}\t{n}\t{c}\t{c / n:.4f}\t[{lo:.4f};{hi:.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
