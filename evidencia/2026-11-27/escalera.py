#!/usr/bin/env python3
"""Escalera de acoplamiento entre las puntas de PR abiertos de un repositorio.

Para cada pareja de puntas ``(a, b)`` este script publica dos cosas:

* ``k`` — cuántas rutas tocan las dos ramas, medidas contra ``merge-base(a, b)``;
* el veredicto del merge de las dos puntas, calculado con el propio paquete
  (:func:`merge_lattice_governor.parejas.pareja`), no con una copia paralela.

La base es **la de la pareja**, nunca el tronco: medir contra el tronco confunde
linaje compartido con colisión.

Emite una línea TSV por pareja —``a``, ``b``, ``k``, ``veredicto``— por la salida
estándar. Sólo corre ``git`` de lectura: cero escrituras en el repositorio que
audita.

Uso:

    PYTHONPATH=. python3 evidencia/2026-11-27/escalera.py REPO PREFIJO [--tope N]

``PREFIJO`` es el prefijo de las refs que son puntas de PR (por ejemplo
``refs/remotes/pr/``) y ``--tope`` limita a las N primeras en orden lexicográfico
para que la corrida quepa en un presupuesto conocido. Con ``--hubs N`` publica
además en la salida de error las N rutas que más parejas comparten: casi siempre
nombran el archivo que hay que partir, no la rama.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

from merge_lattice_governor import parejas
from merge_lattice_governor import repo as R


def puntas(repo: str, prefijo: str, tope: int | None) -> list[str]:
    salida = R.git(repo, "for-each-ref", "--format=%(refname)", prefijo)
    refs = R.exigir(salida, f"for-each-ref {prefijo}").split()
    refs.sort()
    return refs[:tope] if tope else refs


def fila(repo: str, a: str, b: str) -> tuple[str, str, int, str, tuple[str, ...]]:
    base = R.base_de_par(repo, a, b)
    if base is None:
        return a, b, 0, parejas.HISTORIAS_AJENAS, ()
    rutas_a = set(R.rutas(repo, base, a))
    rutas_b = set(R.rutas(repo, base, b))
    comunes = tuple(sorted(rutas_a & rutas_b))
    return a, b, len(comunes), parejas.pareja(repo, a, b).clase, comunes


def hubs(filas: list[tuple[str, str, int, str, tuple[str, ...]]]) -> list[tuple[str, int, int]]:
    """Rutas compartidas por más parejas: ``(ruta, parejas, de ellas en conflicto)``."""
    total: dict[str, int] = {}
    rojas: dict[str, int] = {}
    for _, _, _, veredicto, comunes in filas:
        for ruta in comunes:
            total[ruta] = total.get(ruta, 0) + 1
            if veredicto == parejas.CONFLICTO_TEXTUAL:
                rojas[ruta] = rojas.get(ruta, 0) + 1
    orden = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(ruta, n, rojas.get(ruta, 0)) for ruta, n in orden]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repo")
    p.add_argument("prefijo")
    p.add_argument("--tope", type=int, default=None)
    p.add_argument("--trabajadores", type=int, default=4)
    p.add_argument(
        "--hubs",
        type=int,
        default=0,
        metavar="N",
        help="publica en stderr las N rutas compartidas por más parejas",
    )
    args = p.parse_args(argv)

    if not R.es_repo(args.repo):
        print(f"no es un repositorio git: {args.repo}", file=sys.stderr)
        return 2

    refs = puntas(args.repo, args.prefijo, args.tope)
    if len(refs) < 2:
        print(f"{args.prefijo} da {len(refs)} punta(s): hacen falta 2", file=sys.stderr)
        return 2

    with ThreadPoolExecutor(max_workers=args.trabajadores) as hilos:
        filas = list(hilos.map(lambda par: fila(args.repo, *par), combinations(refs, 2)))

    for a, b, k, veredicto, _ in filas:
        print(f"{a}\t{b}\t{k}\t{veredicto}")

    if args.hubs:
        print("ruta\tparejas\ten_conflicto", file=sys.stderr)
        for ruta, n, rojas in hubs(filas)[: args.hubs]:
            print(f"{ruta}\t{n}\t{rojas}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
