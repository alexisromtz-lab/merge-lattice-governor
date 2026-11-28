"""La etiqueta y el manifiesto tienen que ser el mismo objeto.

Publicar es un acto público irreversible —un número de versión en PyPI no se
recicla—, así que la guarda no vive dentro del YAML como una expresión que
nadie ejecuta: vive aquí, se corre **antes** de construir, y un test la
ejercita en los dos sentidos (RC 0 cuando cuadra, RC 1 cuando no).

RC 0 · la etiqueta es ``v<__version__>``
RC 1 · no cuadra; no se construye ni se sube nada
RC 2 · no hay etiqueta que verificar (una corrida sin tag nunca publica)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from merge_lattice_governor import __version__  # noqa: E402


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="verificar-etiqueta", description=__doc__.splitlines()[0])
    p.add_argument("etiqueta", nargs="?", default=os.environ.get("GITHUB_REF_NAME", ""))
    a = p.parse_args(argv)

    if not a.etiqueta:
        print("RC 2 · sin etiqueta: nada que verificar, nada que publicar")
        return 2

    esperada = f"v{__version__}"
    if a.etiqueta != esperada:
        print(f"RC 1 · la etiqueta {a.etiqueta!r} no es {esperada!r}: no se publica")
        return 1

    print(f"RC 0 · etiqueta {a.etiqueta} == __version__ {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
