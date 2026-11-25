"""Matriz de conmutatividad por parejas.

Dos ramas conmutan si su merge textual es limpio **y** no declaran el mismo
ordinal de test en la misma clase. La base se calcula por pareja: usar una base
global para N ramas de un mismo tronco inventa conflictos que no existen
(medido en el corpus: 76 rojos con base global, 1 con base por pareja).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from . import repo as R
from .sombra import colisiones, metodos, nuevos

CONMUTA_LIMPIO = "CONMUTA_LIMPIO"
COLISION_SIMBOLICA_AST = "COLISION_SIMBOLICA_AST"
CONFLICTO_TEXTUAL = "CONFLICTO_TEXTUAL"
HISTORIAS_AJENAS = "HISTORIAS_AJENAS"


@dataclass(frozen=True)
class Pareja:
    a: str
    b: str
    base: str | None
    textual: tuple[str, ...] = ()
    simbolica: tuple[str, ...] = ()

    @property
    def clase(self) -> str:
        if self.base is None:
            return HISTORIAS_AJENAS
        if self.textual:
            return CONFLICTO_TEXTUAL
        if self.simbolica:
            return COLISION_SIMBOLICA_AST
        return CONMUTA_LIMPIO

    def describe(self) -> str:
        if self.clase == CONFLICTO_TEXTUAL:
            return f"{self.clase}: {', '.join(self.textual)}"
        if self.clase == COLISION_SIMBOLICA_AST:
            return f"{self.clase}: {', '.join(self.simbolica)}"
        return self.clase


def _simbolicas(repo: str, a: str, b: str, base: str) -> tuple[str, ...]:
    comunes = sorted(
        {r for r in R.rutas(repo, base, a) if r.endswith(".py")}
        & {r for r in R.rutas(repo, base, b) if r.endswith(".py")}
    )
    hallazgos: list[str] = []
    for ruta in comunes:
        fuente_a = R.leer(repo, a, ruta)
        fuente_b = R.leer(repo, b, ruta)
        if fuente_a is None or fuente_b is None:
            continue
        base_src = R.leer(repo, base, ruta) or ""
        heredados = metodos(base_src)
        nuevos_a = nuevos(heredados, metodos(fuente_a))
        nuevos_b = nuevos(heredados, metodos(fuente_b))
        for metodo_a, metodo_b in colisiones(nuevos_a, nuevos_b, incluir_mismo_nombre=True):
            hallazgos.append(
                f"{ruta}:{metodo_a.clase}.{metodo_a.nombre} vs {ruta}:{metodo_b.clase}.{metodo_b.nombre}"
            )
    return tuple(hallazgos)


def pareja(repo: str, a: str, b: str) -> Pareja:
    base = R.base_de_par(repo, a, b)
    if base is None:
        return Pareja(a=a, b=b, base=None)
    return Pareja(
        a=a,
        b=b,
        base=base,
        textual=R.rutas_en_conflicto(repo, base, a, b),
        simbolica=_simbolicas(repo, a, b, base),
    )


def matriz(repo: str, refs: list[str]) -> list[Pareja]:
    return [pareja(repo, a, b) for a, b in combinations(refs, 2)]


def resumen(parejas: list[Pareja]) -> dict[str, int]:
    cuenta = {CONMUTA_LIMPIO: 0, COLISION_SIMBOLICA_AST: 0, CONFLICTO_TEXTUAL: 0, HISTORIAS_AJENAS: 0}
    for p in parejas:
        cuenta[p.clase] += 1
    return cuenta


def incompatibles(parejas: list[Pareja]) -> list[Pareja]:
    return [p for p in parejas if p.clase not in (CONMUTA_LIMPIO,)]
