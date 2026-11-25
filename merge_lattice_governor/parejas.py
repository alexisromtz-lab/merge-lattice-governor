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
from .sombra import Metodo, colisiones, leer, metodos, nuevos

CONMUTA_LIMPIO = "CONMUTA_LIMPIO"
COLISION_SIMBOLICA_AST = "COLISION_SIMBOLICA_AST"
CONFLICTO_TEXTUAL = "CONFLICTO_TEXTUAL"
HISTORIAS_AJENAS = "HISTORIAS_AJENAS"
NO_MEDIDO = "NO_MEDIDO"


@dataclass(frozen=True)
class Pareja:
    a: str
    b: str
    base: str | None
    textual: tuple[str, ...] = ()
    simbolica: tuple[str, ...] = ()
    ilegibles: tuple[str, ...] = ()

    @property
    def clase(self) -> str:
        if self.base is None:
            return HISTORIAS_AJENAS
        if self.textual:
            return CONFLICTO_TEXTUAL
        if self.simbolica:
            return COLISION_SIMBOLICA_AST
        if self.ilegibles:
            return NO_MEDIDO
        return CONMUTA_LIMPIO

    def describe(self) -> str:
        if self.clase == CONFLICTO_TEXTUAL:
            return f"{self.clase}: {', '.join(self.textual)}"
        if self.clase == COLISION_SIMBOLICA_AST:
            return f"{self.clase}: {', '.join(self.simbolica)}"
        if self.clase == NO_MEDIDO:
            return f"{self.clase}: {', '.join(self.ilegibles)}"
        return self.clase


def _simbolicas(repo: str, a: str, b: str, base: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(colisiones, archivos ilegibles) sobre las rutas .py que las dos ramas tocan."""
    comunes = sorted(
        {r for r in R.rutas(repo, base, a) if r.endswith(".py")}
        & {r for r in R.rutas(repo, base, b) if r.endswith(".py")}
    )
    hallazgos: list[str] = []
    ilegibles: list[str] = []
    for ruta in comunes:
        fuente_a = R.leer(repo, a, ruta)
        fuente_b = R.leer(repo, b, ruta)
        if fuente_a is None or fuente_b is None:
            continue
        base_src = R.leer(repo, base, ruta) or ""
        heredados = metodos(base_src)
        metodos_a, fallo_a = leer(fuente_a, ruta)
        metodos_b, fallo_b = leer(fuente_b, ruta)
        for fallo in (fallo_a, fallo_b):
            if fallo and fallo not in ilegibles:
                ilegibles.append(fallo)
        nuevos_a = nuevos(heredados, metodos_a)
        nuevos_b = nuevos(heredados, metodos_b)
        for metodo_a, metodo_b in colisiones(nuevos_a, nuevos_b, incluir_mismo_nombre=True):
            hallazgos.append(
                f"{_testigo(ruta, metodo_a, a)} vs {_testigo(ruta, metodo_b, b)}"
            )
    return tuple(hallazgos), tuple(ilegibles)


def _testigo(ruta: str, metodo: Metodo, ref: str) -> str:
    """`ruta:linea@ref Clase.metodo`: la línea es de esa rama, no del par."""
    corto = ref.rsplit("/", 1)[-1]
    return f"{ruta}:{metodo.linea}@{corto} {metodo.rotulo()}"


def pareja(repo: str, a: str, b: str) -> Pareja:
    base = R.base_de_par(repo, a, b)
    if base is None:
        return Pareja(a=a, b=b, base=None)
    simbolica, ilegibles = _simbolicas(repo, a, b, base)
    return Pareja(
        a=a,
        b=b,
        base=base,
        textual=R.rutas_en_conflicto(repo, base, a, b),
        simbolica=simbolica,
        ilegibles=ilegibles,
    )


def sola(repo: str, tronco: str, ref: str) -> tuple[str, ...]:
    """Dos ``test_06`` en la misma clase dentro de **una** rama.

    El mismo predicado que entre ramas, aplicado a la propia rama: un merge
    anterior ya pudo dejar el duplicado dentro. Sin esto, ``--ref`` único
    imprime una matriz de cero pares y la llama limpia.
    """
    base = R.base_de_rama(repo, tronco, ref)
    hallazgos: list[str] = []
    for ruta in [r for r in R.rutas(repo, base, ref) if r.endswith(".py")]:
        fuente = R.leer(repo, ref, ruta)
        if fuente is None:
            continue
        metodos_ref, fallo = leer(fuente, ruta)
        if fallo:
            hallazgos.append(fallo)
            continue
        propios = nuevos(metodos(R.leer(repo, base, ruta) or ""), metodos_ref)
        for metodo_a, metodo_b in colisiones(propios, propios, incluir_mismo_nombre=True):
            hallazgos.append(
                f"{_testigo(ruta, metodo_a, ref)} vs {_testigo(ruta, metodo_b, ref)}"
            )
    return tuple(hallazgos)


def matriz(repo: str, refs: list[str]) -> list[Pareja]:
    return [pareja(repo, a, b) for a, b in combinations(refs, 2)]


def resumen(parejas: list[Pareja]) -> dict[str, int]:
    cuenta = {
        CONMUTA_LIMPIO: 0,
        COLISION_SIMBOLICA_AST: 0,
        CONFLICTO_TEXTUAL: 0,
        HISTORIAS_AJENAS: 0,
        NO_MEDIDO: 0,
    }
    for p in parejas:
        cuenta[p.clase] += 1
    return cuenta


def incompatibles(parejas: list[Pareja]) -> list[Pareja]:
    return [p for p in parejas if p.clase not in (CONMUTA_LIMPIO,)]
