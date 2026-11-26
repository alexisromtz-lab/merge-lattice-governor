"""CLI: matriz de conmutatividad, plan exacto y recibo."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from . import __version__
from . import lotes as L
from . import parejas as P
from . import rebase as B
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
        "--jobs",
        type=int,
        default=0,
        help="hilos para la matriz de parejas (0 = auto, acotado a 8; 1 = serie)",
    )
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
    p.add_argument(
        "--prescribir",
        action="store_true",
        help="publica el acto de cada rama (rebasar libre / con riesgo) por clases de rename",
    )
    p.add_argument(
        "--copias",
        action="store_true",
        help="detecta copias desde fuentes no modificadas (--find-copies-harder): 32× más lento "
        "y sobre 155 ramas medidas no cambió un solo veredicto ni cubrió una ruta de conflicto",
    )
    p.add_argument(
        "--lotes",
        action="store_true",
        help="agrupa las ramas en corridas de CI sin choque posible (soporte disjunto, sin merges)",
    )
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--sin-optimizar",
        action="store_true",
        help="corre el merge también cuando el soporte es disjunto: diferencial del teorema",
    )
    p.add_argument(
        "--sin-friccion",
        action="store_true",
        help="no mide el choque de cada rama con el tronco (una menos por rama atrasada)",
    )
    p.add_argument(
        "--ignorar-driver",
        action="store_true",
        help="no lee .gitattributes: el veredicto es el del merge genérico puro (aproximación)",
    )
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--version", action="version", version=f"merge-lattice-governor {__version__}")
    return p


def _hilos(jobs: int) -> int:
    """Hilos efectivos: ``0`` es auto y no promete más de lo que la máquina da."""
    if jobs and jobs > 0:
        return jobs
    return max(1, min(8, os.cpu_count() or 1))


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


def _textual_en_plan(matriz: Sequence[P.Pareja], orden: Sequence[str]) -> list[dict]:
    """Pares textuales con **las dos** ramas dentro del plan.

    Un conflicto textual no excluye la rama (se resuelve a mano), pero el
    ``git merge`` del plan se detiene en ese paso. Sin decirlo, el OPERAR que
    esta herramienta imprime falla en la primera rama del par.
    """
    posicion = {nombre: i for i, nombre in enumerate(orden)}
    filas: list[dict] = []
    for p in P.incompatibles(matriz):
        if p.clase != P.CONFLICTO_TEXTUAL:
            continue
        if p.a not in posicion or p.b not in posicion:
            continue
        tarde, antes = (p.a, p.b) if posicion[p.a] > posicion[p.b] else (p.b, p.a)
        filas.append(
            {"rama": tarde, "posicion": posicion[tarde] + 1, "con": antes, "rutas": list(p.propias)}
        )
    return sorted(filas, key=lambda f: (f["posicion"], f["rama"]))


def _texto(repo: str, base: str, ramas: list[Rama], matriz: list[P.Pareja], plan, h0: float, ratio: float, banda: float, criterio: str, fric=None, prescripcion=None) -> str:
    lineas: list[str] = []
    tronco = R.resolver(repo, base)[:8]
    lineas.append(f"SUJETO · {len(ramas)} ramas · tronco {base} ({tronco})")
    lineas.append(f"HOLGURA INICIAL {h0:+.2f} · banda {banda} · ratio {ratio}")
    lineas.append(f"CRITERIO · peso {criterio} · desempate: holgura final")
    lineas.append("")
    lineas.extend(_texto_ramas(ramas, ratio, banda, fric))
    lineas.append("")

    if matriz:
        cuenta = P.resumen(matriz)
        lineas.append(f"MATRIZ DE PAREJAS ({len(matriz)} pares)")
        lineas.append(f"  {P.CONMUTA_LIMPIO} {cuenta[P.CONMUTA_LIMPIO]} · "
                      f"{P.COLISION_SIMBOLICA_AST} {cuenta[P.COLISION_SIMBOLICA_AST]} · "
                      f"{P.CONFLICTO_TEXTUAL} {cuenta[P.CONFLICTO_TEXTUAL]} · "
                      f"{P.NO_MEDIDO} {cuenta[P.NO_MEDIDO]} · "
                      f"{P.HISTORIAS_AJENAS} {cuenta[P.HISTORIAS_AJENAS]}")
        lineas.extend(_complementos(matriz))
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

    if prescripcion:
        lineas.extend(B.texto(prescripcion))
        lineas.append("")

    if plan.orden:
        por_nombre = {r.nombre: r for r in ramas}
        choques: dict[str, list[dict]] = {}
        for fila in _textual_en_plan(matriz, plan.orden):
            choques.setdefault(fila["rama"], []).append(fila)
        lineas.append("OPERAR (un solo push al final)")
        for nombre in plan.orden:
            lineas.append(
                f'  git -C {repo} merge --no-ff {por_nombre[nombre].ref} -m "merge: {nombre}"'
            )
            for fila in choques.get(nombre, []):
                lineas.append(
                    f"    ⚠ conflicto textual con {fila['con']} en "
                    f"{', '.join(fila['rutas'])}: el merge se detiene, resuelve y commitea"
                )
    return "\n".join(lineas)


def _rama_json(rama: Rama, ratio: float, banda: float, *, con_masa: bool,
               fric: dict[str, tuple[str, ...]] | None = None) -> dict:
    """Una sola forma de ``ramas[]`` en los tres modos.

    Sin masa la clave viaja con ``null``, no con un cero ni con la clave ausente:
    un cero se suma y una clave ausente no se distingue de una versión vieja.
    ``friccion_con_tronco`` sigue la misma regla: ``[]`` es «medido y sin choque»,
    ``null`` es «no medido».
    """
    return {
        "ref": rama.ref,
        "base": rama.base or None,
        "arnes": rama.masa.arnes if con_masa else None,
        "vivo": rama.masa.vivo if con_masa else None,
        "sim": rama.masa.sim if con_masa else None,
        "delta_holgura": rama.masa.delta(ratio, banda) if con_masa else None,
        "friccion_con_tronco": (
            None if fric is None else list(fric.get(rama.ref, ()))
        ),
    }


def _prescripcion_json(prescripciones) -> list[dict] | None:
    """``null`` es «no pedido», no «ninguna rama necesita acto»."""
    if prescripciones is None:
        return None
    return [
        {
            "ref": p.ref,
            "atras": p.atras,
            "estado": p.estado,
            "clases_comunes": list(p.clases),
            "riesgos": list(p.riesgos),
            "merges": p.merges,
        }
        for p in prescripciones
    ]


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
         "identicos": list(p.identicos), "ilegibles": list(p.ilegibles),
         "driver": list(p.driver), "decision": p.decision,
         "prefijo": list(p.prefijo),
         "atribucion": p.atribucion}
        for p in matriz
    ]


def _complementos(matriz: Sequence[P.Pareja]) -> list[str]:
    """Decisiones, atribución y rutas con driver: el marco de cada veredicto."""
    if not matriz:
        return []
    lineas: list[str] = []
    dec = P.decisiones(matriz)
    lineas.append(
        f"  DECISIÓN · {P.TEOREMA} {dec[P.TEOREMA]} (soporte disjunto, sin merge) · "
        f"{P.MEDIDO} {dec[P.MEDIDO]} (merge a tres bandas)"
    )
    atr = P.atribucion(matriz)
    if atr[P.ATRIBUCION_TRONCO] or atr[P.ATRIBUCION_PAR]:
        lineas.append(
            f"  ATRIBUCIÓN · {P.ATRIBUCION_TRONCO} {atr[P.ATRIBUCION_TRONCO]} "
            f"(reparación: rebasar) · {P.ATRIBUCION_PAR} {atr[P.ATRIBUCION_PAR]} "
            f"(el orden no lo repara)"
        )
    con = P.con_driver(matriz)
    if con:
        rutas = sorted({r.split(" merge=")[0] for p in con for r in p.driver})
        nombres = sorted({r.split("merge=")[-1] for p in con for r in p.driver})
        lineas.append(
            f"  DRIVER · {len(con)} pareja(s) deciden en ruta que tocan los dos lados "
            f"({len(rutas)} ruta(s) con merge={', '.join(nombres)}): NO_MEDIDO, el driver "
            "corre en el merge real y aquí no se ejecuta"
        )
    return lineas


def _texto_ramas(ramas: Sequence[Rama], ratio: float, banda: float,
                 fric: dict[str, tuple[str, ...]] | None) -> list[str]:
    cabecera = f"  {'rama':<38}{'base':<10}{'arnes':>8}{'vivo':>8}{'sim':>8}{'Δholgura':>12}"
    if fric is not None:
        cabecera += f"{'tronco':>8}"
    lineas = [cabecera]
    for rama in ramas:
        m = rama.masa
        fila = (
            f"  {rama.nombre:<38}{rama.base:<10}{m.arnes:>8}{m.vivo:>8}{m.sim:>8}"
            f"{m.delta(ratio, banda):>+12.2f}"
        )
        if fric is not None:
            fila += f"{len(fric.get(rama.ref, ())):>8}"
        lineas.append(fila)
    return lineas


def _carga_json(repo, base, ramas, matriz, plan, h0, ratio, banda, criterio,
                fric=None, prescripcion=None) -> dict:
    return {
        "schema": ESQUEMA,
        "version": __version__,
        "repo": repo,
        "base": base,
        "criterio": criterio,
        "holgura_inicial": round(h0, 4),
        "ley": {"banda_techo": banda, "ratio_linea_base": ratio},
        "prescripcion": _prescripcion_json(prescripcion),
        "ramas": [_rama_json(r, ratio, banda, con_masa=True, fric=fric) for r in ramas],
        "parejas": _parejas_json(matriz),
        "ilegibles": _ilegibles(*(p.ilegibles for p in matriz)),
        "resumen": P.resumen(matriz),
        "decisiones": P.decisiones(matriz),
        "atribucion": P.atribucion(matriz),
        "duplicados": P.duplicados(matriz),
        "sola": None,
        "plan": {
            "exacto": plan.exacto,
            "orden": list(plan.orden),
            "trayectoria": list(plan.trayectoria),
            "excluidas": list(plan.excluidas),
            "holgura_final": round(plan.holgura_final, 4),
            "textual_en_plan": _textual_en_plan(matriz, plan.orden),
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

    sop = {"a": ("x.py",), "b": ("x.py",), "c": ("y.py",)}
    grupos = L.colorear(L.choques(sop))
    assert len(grupos) == 2, grupos
    assert not any({"a", "b"} <= set(g) for g in grupos), "dos ramas sobre x.py nunca comparten lote"
    assert L.cota_inferior(sop) == 2, "dos ramas sobre x.py son una clique de tamaño 2"

    print("self-test OK · corredor -1020.35 → +46.62 · pago primero · prefijo estricto")
    print("self-test OK · lotes: coloración sin arista intra-lote · cota inferior = clique de archivo")
    return RC_OK


def _texto_matriz(repo: str, base: str, ramas: list[Rama], matriz: list[P.Pareja], fric=None,
                  prescripcion=None) -> str:
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
    lineas.extend(_complementos(matriz))
    for p in P.incompatibles(matriz):
        lineas.append(f"  · {p.a} × {p.b}  {p.describe()}")
    if prescripcion:
        lineas.append("")
        lineas.extend(B.texto(prescripcion))
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


def _texto_sola(repo: str, base: str, ref: str, hallazgos: tuple[str, ...],
                prescripcion=None) -> str:
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
    if prescripcion:
        lineas.append("")
        lineas.extend(B.texto(prescripcion))
    lineas.extend(
        [
            "",
            "RC · 0 medida y sin duplicados · 1 duplicados internos · 2 NO_MEDIDO.",
            "Para planificar el aterrizaje de una sola rama usa --sin-parejas.",
        ]
    )
    return "\n".join(lineas)


def _lotes_json(l: L.Lotes, args) -> dict:
    return {
        "schema": ESQUEMA,
        "version": __version__,
        "repo": args.repo,
        "base": args.base,
        "criterio": "lotes: coloración del grafo de choque por soporte de archivo (sin merges)",
        "marco": L.MARCO,
        "ramas": list(l.ramas),
        "pares": {"total": l.pares, "seguros": l.pares_seguros, "no_seguros": l.pares_no_seguros},
        "lotes": [list(g) for g in l.lotes],
        "numero_de_lotes": len(l.lotes),
        "cota_inferior": l.cota_inferior,
        "minimo_probado": l.exacto,
        "soportes": {ref: list(rutas) for ref, rutas in l.soportes.items()},
        "prescripcion": _prescripcion_json(
            B.prescribir(args.repo, args.base, args.ref, copias=args.copias) if args.prescribir else None
        ),
    }


def _modo_lotes(args) -> int:
    try:
        resultado = L.lotes(args.repo, args.base, args.ref)
        oid = R.resolver(args.repo, args.base)[:8]
    except R.ErrorGit as error:
        print(f"RC 2 · {error}", file=sys.stderr)
        return RC_ENTRADA
    if args.json:
        print(json.dumps(_lotes_json(resultado, args), ensure_ascii=False, indent=2))
    else:
        print(L.texto(resultado, args.base, oid))
        if args.prescribir:
            print()
            print(B.texto(B.prescribir(args.repo, args.base, args.ref, copias=args.copias)))
    return RC_OK


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        return _self_test()

    if args.prescribir and args.holgura_inicial is None and not args.lotes:
        # La prescripción contesta «qué acto pide cada rama», no «en qué orden aterrizan»: sin
        # cubeta no hay plan posible, así que pedirle una es pedir un dato que su salida no usa.
        # El modo pasa a auditoría, y con él se omite la matriz —que son N² merges de lectura—.
        args.sin_plan = True
        args.sin_parejas = True

    if not args.ref:
        print("RC 2 · falta --ref: sin población no hay denominador", file=sys.stderr)
        return RC_ENTRADA
    if args.sin_plan and args.sin_parejas and not args.prescribir and not args.lotes:
        print("RC 2 · --sin-plan y --sin-parejas no dejan nada que medir", file=sys.stderr)
        return RC_ENTRADA
    if len(args.ref) < 2 and not args.sin_parejas and not args.sin_plan and not args.prescribir and not args.lotes:
        print(
            "RC 2 · la matriz necesita >=2 ramas: una matriz de 0 pares no es una matriz limpia;"
            " usa --sin-parejas para planificar una sola rama o --sin-plan --ref R para auditarla",
            file=sys.stderr,
        )
        return RC_ENTRADA
    if args.holgura_inicial is None and not args.sin_plan and not args.lotes:
        print("RC 2 · falta --holgura-inicial: una solvencia sin punto de partida es una ficción", file=sys.stderr)
        return RC_ENTRADA
    if not R.es_repo(args.repo):
        print(f"RC 2 · no es un repositorio git: {args.repo}", file=sys.stderr)
        return RC_ENTRADA

    if args.lotes:
        return _modo_lotes(args)

    try:
        ramas = _ramas(args.repo, args.base, args.ref, args.ratio, args.banda, con_masa=not args.sin_plan)
        pesos = _pesos(args.prioridad, ramas)
        prescripcion = (
            B.prescribir(args.repo, args.base, args.ref, copias=args.copias) if args.prescribir else None
        )
    except (R.ErrorGit, ValueError) as error:
        print(f"RC 2 · {error}", file=sys.stderr)
        return RC_ENTRADA

    matriz: list[P.Pareja] = []
    fric: dict[str, tuple[str, ...]] | None = None
    if not args.sin_parejas:
        try:
            matriz = P.matriz(
                args.repo, args.ref,
                optimizar=not args.sin_optimizar,
                driver=not args.ignorar_driver,
                jobs=_hilos(args.jobs),
            )
            if not args.sin_friccion:
                fric = P.fricciones(args.repo, args.base, args.ref)
                matriz = P.anotar(matriz, fric)
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
                    "prescripcion": _prescripcion_json(prescripcion),
                    "ramas": [
                        _rama_json(r, args.ratio, args.banda, con_masa=False, fric=fric)
                        for r in ramas
                    ],
                    "parejas": [],
                    "ilegibles": _ilegibles(hallazgos),
                    "resumen": None,
                    "decisiones": {},
                    "atribucion": {},
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
            print(_texto_sola(args.repo, args.base, args.ref[0], hallazgos, prescripcion))
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
                    "prescripcion": _prescripcion_json(prescripcion),
                    "ramas": [
                        _rama_json(r, args.ratio, args.banda, con_masa=False, fric=fric)
                        for r in ramas
                    ],
                    "parejas": _parejas_json(matriz),
                    "ilegibles": _ilegibles(*(p.ilegibles for p in matriz)),
                    "resumen": P.resumen(matriz),
                    "decisiones": P.decisiones(matriz),
                    "atribucion": P.atribucion(matriz),
                    "duplicados": P.duplicados(matriz),
                    "sola": None,
                    "plan": None,
                },
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print(_texto_matriz(args.repo, args.base, ramas, matriz, fric, prescripcion))
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
        print(json.dumps(_carga_json(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda, criterio, fric, prescripcion), ensure_ascii=False, indent=2))
    else:
        print(_texto(args.repo, args.base, ramas, matriz, plan, args.holgura_inicial, args.ratio, args.banda, criterio, fric, prescripcion))

    rc_matriz = _rc_matriz(matriz)
    if rc_matriz == RC_ENTRADA:
        return RC_ENTRADA
    if not plan.completo or rc_matriz == RC_PARADA:
        return RC_PARADA
    return RC_OK


if __name__ == "__main__":
    raise SystemExit(main())
