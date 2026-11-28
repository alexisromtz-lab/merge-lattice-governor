#!/usr/bin/env python3
"""Selecciona la muestra sembrada de puntas de PR de entre la población abierta.

Lee de la entrada estándar los números de PR abiertos —uno por línea, la
población en el instante del ``gh pr list``— y escribe la muestra, ordenada y
separada por comas, para que el paso de ``git fetch`` baje **sólo** esas puntas.
Sin esto habría que clonar cientos de cabezas para tirar el 60 % a la basura.

Uso:

    gh pr list -R OWNER/REPO --state open --limit 1000 --json number \
        --jq '.[].number' | python3 muestra.py --tamano 40 --semilla 20261128

La selección es ``random.Random(semilla).sample`` sobre la población ordenada
numéricamente: misma semilla y misma población ⇒ misma muestra, verificable.
"""

from __future__ import annotations

import argparse
import random
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tamano", type=int, required=True, metavar="N")
    p.add_argument("--semilla", type=int, default=0)
    args = p.parse_args(argv)

    poblacion = sorted({int(x) for x in sys.stdin.read().split() if x.strip()})
    if args.tamano > len(poblacion):
        print(f"--tamano {args.tamano} > {len(poblacion)} PRs abiertas", file=sys.stderr)
        return 2
    elegidas = sorted(random.Random(args.semilla).sample(poblacion, args.tamano))
    print(f"poblacion={len(poblacion)}", file=sys.stderr)
    print(",".join(str(n) for n in elegidas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
