"""CLI: matriz de conmutatividad, plan exacto y recibo."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from . import parejas as P
from . import repo as R
from .ley import BANDA_TECHO, RATIO_LINEA_BASE, Masa
from .secuencia import MAXIMO_EXACTO, Rama, planificar

ESQUEMA = "merge-lattice-governor/1"

RC_OK = 0
RC_PARADA = 1
RC_ENTRADA = 2


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="merge-lattice-governor",
        description="Plan exacto del orden de aterrizaje de ramas git bajo solvencia por prefijo.",
    )
    p.add_argument("--repo", default=".", help="repositorio git (por defecto: .)")
    p.add_argument("--base", default="origin/main", help="tronco de referencia (por defecto: origin/main)")
    p.add_argument("--ref", action="append", default=[], help="rama a aterrizar; repetible")
    p.add_argument(
        "--holgura-inicial",
        type=float,
        default=None,
        help="holgura medida antes de la primera rama; sin ella no hay solvencia que decidir",
    )
    p.add_argument("--ratio", type=float, default=RATIO_LINEA_BASE)
    p.add_argument("--banda", type=float, default=BANDA_TECHO)
    p.add_argument("--max-n", type=int, default=MAXIMO_EXACTO, help="cota del DP exacto")
    p.add_argument("--sin-parejas", action="store_true", help="omite la matriz (N² merges de lectura)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--version", action="version", version=f"merge-lattice-governor {__version__}")
    return p


def _intocables(ramas: list, matriz: list) -> dict[int, int]:
    """Máscara de ramas que no pueden coexistir, por índice de `ramas`.

    Una colisión simbólica no la arregla el orden: si a y b declaran el mismo
    test, sólo puede aterrizar una. El planificador recibe esa restricción como
    grafo, no como preferencia.
    """
    indice = {r.clave: i for i, r in enumerate(ramas)}
    mascaras: dict[int, int] = {}
    for pareja in P.incompatibles(matriz):
        if pareja.clase != P.COLISION_SIMBOLICA_AST:
            continue
        i, j = indice.get(pareja.a), indice.get(pareja.b)
        if i is None or j is None or i == j:
            continue
        mascaras[i] = mascaras.get(i, 0) | (1 << j)
        mascaras[j] = mascaras.get(j, 0) | (1 << i)
    return mascaras


def _ramas(repo: str, base: str, refs: list[str], ratio: float, banda: float) -> list[Rama]:
    salida: list[Rama] = []
    for ref in refs:
        R.resolver(repo, ref)
        base_rama = R.base_de_rama(repo, base, ref)
        masa = R.masa(repo, base_rama, ref)
        salida.append(Rama(nombre=ref, masa=masa, ref=ref, base=base_rama[:8]))
    return salida


def _texto(repo: str, base: str, ramas: list[Rama], matriz: list[P.Pareja], plan, h0: float, ratio: float, banda: float) -> str:
    lineas: list[str] = []
    tronco = R.resolver(repo, base)[:8]
    lineas.append(f"SUJETO · {len(ramas)} ramas · tronco {base} ({tronco})")
    lineas.append(f"HOLGURA INICIAL {h0:+.2f} · banda {banda} · ratio {ratio}")
    lineas.append("")
    lineas.append(f"  {'rama':<38}{'base':<10}{'arnes':>8}{'vivo':>8}{'sim':>8}{'Δholgura':>12}")
    for rama in ramas:
        m = rama.masa
        lineas.append(
            f"  {rama.nombre:<38}{rama.base:<10}{m.arnes:>8}{m.vivo:>8}{m.sim:>8}"
            f"{m.delta(ratio, banda):>+12.2f}"
        )
    lineas.append("")

    if matriz:
        cuenta = P.resumen(matriz)
        lineas.append(f"MATRIZ DE PAREJAS ({len(matriz)} pares)")
        lineas.append(f"  {P.CONMUTA_LIMPIO} {cuenta[P.CONMUTA_LIMPIO]} · "
                      f"{P.COLISION_SIMBOLICA_AST} {cuenta[P.COLISION_SIMBOLICA_AST]} · "
                      f"{P.CONFLICTO_TEXTUAL} {cuenta[P.CONFLICTO_TEXTUAL]} · "
                      f"{P.HISTORIAS_AJENAS} {cuenta[P.HISTORIAS_AJENAS]}")
        for p in P.incompatibles(matriz):
            lineas.append(f"  · {p.a} × {p.b}  {p.describe()}")
        lineas.append("")

    etiqueta = "PLAN EXACTO" if plan.exacto else "PLAN VORAZ (fuera de la cota exacta)"
    lineas.append(f"{etiqueta} · {plan.integradas}/{len(ramas)} integradas")
    holgura = plan.holgura_inicial
    for posicion, (nombre, tras) in enumerate(zip(plan.orden, plan.trayectoria), start=1):
        lineas.append(f"  {posicion}. {nombre:<36}{holgura:>+12.2f} → {tras:>+12.2f}")
        holgura = tras
    if plan.excluidas:
        lineas.append(f"  excluidas: {', '.join(plan.excluidas)}")
    lineas.append(f"  holgura final {plan.holgura_final:+.2f}")
    lineas.append("")

    if plan.orden:
        por_nombre = {r.nombre: r for r in ramas}
        lineas.append("OPERAR (un solo push al final)")
        for nombre in plan.orden:
            lineas.append(
                f'  git -C {repo} merge --no-ff {por_nombre[nombre].ref} -m "merge: {nombre}"'
            )
    return "\n".join(lineas)


def _carga_json(repo, base, ramas, matriz, plan, h0, ratio, banda) -> dict:
    return {
        "schema": ESQUEMA,
        "version": __version__,
        "repo": repo,
        "base": base,
        "holgura_inicial": round(h0, 4),
        "ley": {"banda_techo": banda, "ratio_linea_base": ratio},
        "ramas": [
            {
                "ref": r.ref,
                "base": r.base,
                "arnes": r.masa.arnes,
                "vivo": r.masa.vivo,
                "sim": r.masa.sim,
                "delta_holgura": r.masa.delta(ratio, banda),
            }
            for r in ramas
        ],
        "parejas": [
            {"a": p.a, "b": p.b, "base": p.base, "clase": p.clase,
             "textual": list(p.textual), "simbolica": list(p.simbolica)}
            for p in matriz
        ],
        "plan": {
            "exacto": plan.exacto,
            "orden": list(plan.orden),
            "trayectoria": list(plan.trayectoria),
            "excluidas": list(plan.excluidas),
            "holgura_final": round(plan.holgura_final, 4),
        },
    }


def _self_test() -> int:
    """Corredor certificado del corpus: la ley y el DP tienen que reproducirlo."""
    trinquete = Masa(arnes=0, vivo=1029, sim=0)
    viernes = [Masa(98, 0, 0), Masa(145, 0, 0), Masa(151, 0, 0)]
    h0 = -1020.35
    ramas = [Rama("trinquete", trinquete)] + [
        Rama(f"viernes-{i}", m) for i, m in enumerate(viernes, start=1)
    ]
    plan = planificar(ramas, h0)
    assert plan.completo, "el corredor certificado debe integrar las 4 ramas"
    assert plan.orden[0] == "trinquete", "el pago va primero: sin él ningún prefijo es solvente"
    assert abs(plan.holgura_final - 46.62) < 0.01, plan.holgura_final
    assert all(h > 0 for h in plan.trayectoria), plan.trayectoria

    sin_pago = planificar(ramas[1:], h0)
    assert sin_pago.integradas == 0, "sin la rama de pago la cubeta no admite nada"

    exigente = planificar([Rama("nula", Masa(0, 0, 0))], 0.0)
    assert exigente.integradas == 0, "holgura exactamente 0 no es solvencia"

    print("self-test OK · corredor -1020.35 → +46.62 · pago primero · prefijo estricto")
    return RC_OK


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        return _self_test()

    if not args.ref:
        print("RC 2 · falta --ref: sin población no hay denominador", file=sys.stderr)
        return RC_ENTRADA
    if args.holgura_inicial is None:
        print("RC 2 · falta --holgura-inicial: una solvencia sin punto de partida es una ficción", file=sys.stderr)
        return RC_ENTRADA
    if not R.es_repo(args.repo):
        print(f"RC 2 · no es un repositorio git: {args.repo}", file=sys.stderr)
        return RC_ENTRADA

    try:
        ramas = _ramas(args.repo, args.base, args.ref, args.ratio, args.banda)
    except R.ErrorGit as error:
        print(f"RC 2 · {error}", file=sys.stderr)
        return RC_ENTRADA

    matriz: list[P.Pareja] = []
    if not args.sin_parejas:
        try:
            matriz = P.matriz(args.repo, args.ref)
        except R.ErrorGit as error:
            print(f"RC 2 · {error}", file=sys.stderr)
            return RC_ENTRADA

    intocables = _intocables(ramas, matriz)
    plan = planificar(
        ramas,
        args.holgura_inicial,
        ratio=args.ratio,
        banda=args.banda,
        maximo_exacto=args.max_n,
        intocables=intocables,
    )

    if args.json:
        print(json.dumps(_carga_json(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda), ensure_ascii=False, indent=2))
    else:
        print(_texto(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda))

    if not plan.completo:
        return RC_PARADA
    if P.incompatibles(matriz):
        return RC_PARADA
    return RC_OK


if __name__ == "__main__":
    raise SystemExit(main())
