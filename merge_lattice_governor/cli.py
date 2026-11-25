"""CLI: matriz de conmutatividad, plan exacto y recibo."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from . import parejas as P
from . import repo as R
from . import sombra as S
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
    p.add_argument(
        "--sin-plan",
        action="store_true",
        help="sólo la matriz: no exige holgura porque un repositorio ajeno no declara esta ley de masa",
    )
    p.add_argument(
        "--prioridad",
        action="append",
        default=[],
        metavar="RAMA=PESO",
        help="peso de una rama en la función objetivo (por defecto 1); repetible",
    )
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


def _ramas(repo: str, base: str, refs: list[str], ratio: float, banda: float, *, con_masa: bool = True) -> list[Rama]:
    salida: list[Rama] = []
    for ref in refs:
        R.resolver(repo, ref)
        if not con_masa:
            salida.append(Rama(nombre=ref, masa=Masa(), ref=ref))
            continue
        base_rama = R.base_de_rama(repo, base, ref)
        masa = R.masa(repo, base_rama, ref)
        salida.append(Rama(nombre=ref, masa=masa, ref=ref, base=base_rama[:8]))
    return salida


def _pesos(cadenas: list[str], ramas: list[Rama]) -> dict[str, float]:
    """``RAMA=PESO`` → pesos. Un nombre que no casa es RC 2, nunca un peso implícito."""
    conocidas = {r.clave for r in ramas}
    pesos: dict[str, float] = {}
    for cadena in cadenas:
        nombre, _, texto = cadena.partition("=")
        if nombre not in conocidas:
            raise ValueError(f"--prioridad {cadena}: no hay rama con ese nombre")
        try:
            pesos[nombre] = float(texto)
        except ValueError:
            raise ValueError(f"--prioridad {cadena}: el peso no es un número") from None
    return pesos


def _criterio(pesos: dict[str, float]) -> str:
    if not pesos:
        return "uniforme (1 por rama)"
    detalle = " ".join(f"{nombre}={peso:g}" for nombre, peso in sorted(pesos.items()))
    return f"declarado · {detalle} · resto 1"


def _texto(repo: str, base: str, ramas: list[Rama], matriz: list[P.Pareja], plan, h0: float, ratio: float, banda: float, criterio: str) -> str:
    lineas: list[str] = []
    tronco = R.resolver(repo, base)[:8]
    lineas.append(f"SUJETO · {len(ramas)} ramas · tronco {base} ({tronco})")
    lineas.append(f"HOLGURA INICIAL {h0:+.2f} · banda {banda} · ratio {ratio}")
    lineas.append(f"CRITERIO · peso {criterio} · desempate: holgura final")
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
                      f"{P.NO_MEDIDO} {cuenta[P.NO_MEDIDO]} · "
                      f"{P.HISTORIAS_AJENAS} {cuenta[P.HISTORIAS_AJENAS]}")
        dup = P.duplicados(matriz)
        lineas.append(
            f"  DUPLICADOS_IDENTICOS {dup['duplicados_identicos']} def(s) en "
            f"{dup['parejas_con_duplicados_identicos']} pareja(s) · mismo nombre y mismo "
            f"cuerpo, ningún test se pierde · 0 aquí significa mirado, no ausente"
        )
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


def _rama_json(rama: Rama, ratio: float, banda: float, *, con_masa: bool) -> dict:
    """Una sola forma de ``ramas[]`` en los tres modos.

    Sin masa la clave viaja con ``null``, no con un cero ni con la clave ausente:
    un cero se suma y una clave ausente no se distingue de una versión vieja.
    """
    return {
        "ref": rama.ref,
        "base": rama.base or None,
        "arnes": rama.masa.arnes if con_masa else None,
        "vivo": rama.masa.vivo if con_masa else None,
        "sim": rama.masa.sim if con_masa else None,
        "delta_holgura": rama.masa.delta(ratio, banda) if con_masa else None,
    }


def _h0_json(h0: float | None) -> float | None:
    return None if h0 is None else round(h0, 4)


def _ilegibles(*fuentes: Sequence[str]) -> list[str]:
    """Rutas ilegibles, siempre presentes: ``[]`` es medida, no ausencia.

    El motivo completo vive en ``parejas[].ilegibles``; aquí se agrega por ruta
    para que la clave no cambie de significado entre modos.
    """
    rutas: set[str] = set()
    for fuente in fuentes:
        for motivo in fuente:
            rutas.add(
                motivo.split(S.MARCA_ILEGIBLE)[0] if S.MARCA_ILEGIBLE in motivo else motivo
            )
    return sorted(rutas)


def _parejas_json(matriz: Sequence[P.Pareja]) -> list[dict]:
    return [
        {"a": p.a, "b": p.b, "base": p.base, "clase": p.clase,
         "textual": list(p.textual), "simbolica": list(p.simbolica),
         "identicos": list(p.identicos), "ilegibles": list(p.ilegibles)}
        for p in matriz
    ]


def _carga_json(repo, base, ramas, matriz, plan, h0, ratio, banda, criterio) -> dict:
    return {
        "schema": ESQUEMA,
        "version": __version__,
        "repo": repo,
        "base": base,
        "criterio": criterio,
        "holgura_inicial": round(h0, 4),
        "ley": {"banda_techo": banda, "ratio_linea_base": ratio},
        "ramas": [_rama_json(r, ratio, banda, con_masa=True) for r in ramas],
        "parejas": _parejas_json(matriz),
        "ilegibles": _ilegibles(*(p.ilegibles for p in matriz)),
        "resumen": P.resumen(matriz),
        "duplicados": P.duplicados(matriz),
        "sola": None,
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


def _texto_matriz(repo: str, base: str, ramas: list[Rama], matriz: list[P.Pareja]) -> str:
    tronco = R.resolver(repo, base)[:8]
    cuenta = P.resumen(matriz)
    lineas = [
        f"SUJETO · {len(ramas)} ramas · tronco {base} ({tronco}) · {len(matriz)} pares",
        "MATRIZ DE PAREJAS",
        f"  {P.CONMUTA_LIMPIO} {cuenta[P.CONMUTA_LIMPIO]} · "
        f"{P.COLISION_SIMBOLICA_AST} {cuenta[P.COLISION_SIMBOLICA_AST]} · "
        f"{P.CONFLICTO_TEXTUAL} {cuenta[P.CONFLICTO_TEXTUAL]} · "
        f"{P.NO_MEDIDO} {cuenta[P.NO_MEDIDO]} · "
        f"{P.HISTORIAS_AJENAS} {cuenta[P.HISTORIAS_AJENAS]}",
    ]
    for p in P.incompatibles(matriz):
        lineas.append(f"  · {p.a} × {p.b}  {p.describe()}")
    lineas.extend(
        [
            "",
            "PLAN: NO_MEDIDO — el techo y el ratio son los de este corpus;",
            "la matriz no los necesita, el plan sí.",
            "RC · 1 si hay COLISION_SIMBOLICA_AST (merge limpio con un test perdido);",
            "2 si hay NO_MEDIDO (no se pudo leer un archivo: no es limpio, es desconocido);",
            "un CONFLICTO_TEXTUAL es hallazgo, no parada.",
        ]
    )
    return "\n".join(lineas)


def _rc_matriz(matriz: list[P.Pareja], *, textual_para: bool = True) -> int:
    """NO_MEDIDO nunca degrada a 0: un archivo ilegible no es un par limpio.

    En el plan, un par que no se puede aterrizar junta hace incompleto el plan:
    ``textual_para``. En ``--sin-plan`` la matriz es el informe y su conflicto
    textual es el dato, no la parada.
    """
    if any(p.clase == P.NO_MEDIDO for p in matriz):
        return RC_ENTRADA
    if any(p.clase == P.COLISION_SIMBOLICA_AST for p in matriz):
        return RC_PARADA
    if textual_para and any(
        p.clase in (P.CONFLICTO_TEXTUAL, P.HISTORIAS_AJENAS) for p in matriz
    ):
        return RC_PARADA
    return RC_OK


def _texto_sola(repo: str, base: str, ref: str, hallazgos: tuple[str, ...]) -> str:
    tronco = R.resolver(repo, base)[:8]
    ilegibles = [h for h in hallazgos if S.MARCA_ILEGIBLE in h]
    choques = [h for h in hallazgos if h not in ilegibles]
    lineas = [
        f"SUJETO · 1 rama · tronco {base} ({tronco}) · {ref}",
        "AUDITORÍA DE RAMA SOLA (sin pareja: el duplicado ya puede venir del merge anterior)",
        f"  duplicados internos {len(choques)} · ilegibles {len(ilegibles)}",
    ]
    for h in choques:
        lineas.append(f"  · {h}")
    for h in ilegibles:
        lineas.append(f"  · NO_MEDIDO {h}")
    lineas.extend(
        [
            "",
            "RC · 0 medida y sin duplicados · 1 duplicados internos · 2 NO_MEDIDO.",
            "Para planificar el aterrizaje de una sola rama usa --sin-parejas.",
        ]
    )
    return "\n".join(lineas)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        return _self_test()

    if not args.ref:
        print("RC 2 · falta --ref: sin población no hay denominador", file=sys.stderr)
        return RC_ENTRADA
    if args.sin_plan and args.sin_parejas:
        print("RC 2 · --sin-plan y --sin-parejas no dejan nada que medir", file=sys.stderr)
        return RC_ENTRADA
    if len(args.ref) < 2 and not args.sin_parejas and not args.sin_plan:
        print(
            "RC 2 · la matriz necesita >=2 ramas: una matriz de 0 pares no es una matriz limpia;"
            " usa --sin-parejas para planificar una sola rama o --sin-plan --ref R para auditarla",
            file=sys.stderr,
        )
        return RC_ENTRADA
    if args.holgura_inicial is None and not args.sin_plan:
        print("RC 2 · falta --holgura-inicial: una solvencia sin punto de partida es una ficción", file=sys.stderr)
        return RC_ENTRADA
    if not R.es_repo(args.repo):
        print(f"RC 2 · no es un repositorio git: {args.repo}", file=sys.stderr)
        return RC_ENTRADA

    try:
        ramas = _ramas(args.repo, args.base, args.ref, args.ratio, args.banda, con_masa=not args.sin_plan)
        pesos = _pesos(args.prioridad, ramas)
    except (R.ErrorGit, ValueError) as error:
        print(f"RC 2 · {error}", file=sys.stderr)
        return RC_ENTRADA

    matriz: list[P.Pareja] = []
    if not args.sin_parejas:
        try:
            matriz = P.matriz(args.repo, args.ref)
        except R.ErrorGit as error:
            print(f"RC 2 · {error}", file=sys.stderr)
            return RC_ENTRADA

    if args.sin_plan and len(args.ref) == 1:
        try:
            hallazgos = P.sola(args.repo, args.base, args.ref[0])
        except R.ErrorGit as error:
            print(f"RC 2 · {error}", file=sys.stderr)
            return RC_ENTRADA
        if args.json:
            print(json.dumps(
                {
                    "schema": ESQUEMA,
                    "version": __version__,
                    "repo": args.repo,
                    "base": args.base,
                    "criterio": "rama sola: duplicado interno, sin pareja",
                    "holgura_inicial": _h0_json(args.holgura_inicial),
                    "ley": {"banda_techo": args.banda, "ratio_linea_base": args.ratio},
                    "ramas": [
                        _rama_json(r, args.ratio, args.banda, con_masa=False)
                        for r in ramas
                    ],
                    "parejas": [],
                    "ilegibles": _ilegibles(hallazgos),
                    "resumen": None,
                    "duplicados": {
                        "duplicados_identicos": 0,
                        "parejas_con_duplicados_identicos": 0,
                    },
                    "sola": {"ref": args.ref[0], "hallazgos": list(hallazgos)},
                    "plan": None,
                },
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print(_texto_sola(args.repo, args.base, args.ref[0], hallazgos))
        if any(S.MARCA_ILEGIBLE in h for h in hallazgos):
            return RC_ENTRADA
        return RC_PARADA if hallazgos else RC_OK

    if args.sin_plan:
        if args.json:
            print(json.dumps(
                {
                    "schema": ESQUEMA,
                    "version": __version__,
                    "repo": args.repo,
                    "base": args.base,
                    "criterio": "matriz sola: sin holgura no hay plan que decidir",
                    "holgura_inicial": _h0_json(args.holgura_inicial),
                    "ley": {"banda_techo": args.banda, "ratio_linea_base": args.ratio},
                    "ramas": [
                        _rama_json(r, args.ratio, args.banda, con_masa=False)
                        for r in ramas
                    ],
                    "parejas": _parejas_json(matriz),
                    "ilegibles": _ilegibles(*(p.ilegibles for p in matriz)),
                    "resumen": P.resumen(matriz),
                    "duplicados": P.duplicados(matriz),
                    "sola": None,
                    "plan": None,
                },
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print(_texto_matriz(args.repo, args.base, ramas, matriz))
        return _rc_matriz(matriz, textual_para=False)

    criterio = _criterio(pesos)
    intocables = _intocables(ramas, matriz)
    plan = planificar(
        ramas,
        args.holgura_inicial,
        ratio=args.ratio,
        banda=args.banda,
        maximo_exacto=args.max_n,
        intocables=intocables,
        pesos=pesos,
    )

    if args.json:
        print(json.dumps(_carga_json(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda, criterio), ensure_ascii=False, indent=2))
    else:
        print(_texto(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda, criterio))

    rc_matriz = _rc_matriz(matriz)
    if rc_matriz == RC_ENTRADA:
        return RC_ENTRADA
    if not plan.completo or rc_matriz == RC_PARADA:
        return RC_PARADA
    return RC_OK


if __name__ == "__main__":
    raise SystemExit(main())
