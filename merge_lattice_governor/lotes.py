"""Lotes: qué ramas caben juntas en una sola corrida de CI, sin un solo merge.

El álgebra es una coloración. Dos ramas son **adyacentes** si sus deltas tocan el
mismo archivo; dos ramas son **seguras** si no lo hacen.

Por qué es sólido: tras rebasar, dos ramas comparten el tronco como base común.
Un merge a tres bandas con **una sola base** no puede chocar entre conjuntos de
cambios disjuntos. Entonces un lote —un conjunto de ramas disjuntas dos a dos—
se integra y se prueba entero sin un solo conflicto.

**PRECONDICIÓN, y es el error caro de esta herramienta:** la relación segura es
un enunciado sobre merges **post-rebase**. Medida contra parejas **pre-rebase**
—donde cada rama conserva su propia base— publica **40 pares seguros falsos** de
105 en la cola del corpus (28-Nov-2026): el choque no viene del otro par, viene
de que la rama está atrasada y el tronco le tocó el mismo archivo. Una rama
atrasada hay que rebasarla; reordenar el plan no lo repara.

Medido en acto real, post-rebase y en clon desechable (28-Nov-2026):
  · 15 ramas de la cola → 10 pares: 9 seguros dieron 9 merges limpios y el único
    no seguro dio el único conflicto, en el archivo exacto declarado — 10/10.
  · 24 ramas ``REBASAR_LIBRE`` rebasadas sobre el tronco → 276 pares, 276
    limpios. Muestra no discriminante (ninguna comparte archivo: cota inferior
    0), pero prueba que el subgrafo rebasado no tiene fricción.

Por qué no es completo: el soporte es por **archivo**. Dos ramas que tocan el
mismo archivo en líneas distintas pueden mergear limpias y aquí se declaran NO
SEGURAS. La relación sirve para **prometer** lotes, no para descartar pares.

El soporte de una rama es ``diff(merge-base(rama, tronco), rama)``, un diff por
rama: el orden de magnitud no es N(N-1)/2 merges sino N.

Cotas del número de lotes: ``χ(G) >= ω(G)``. La clique máxima se acota por abajo de
forma exacta y gratis: todas las ramas que tocan un mismo archivo son adyacentes
dos a dos, así que ``ω(G) >= max_archivo |{ramas que lo tocan}|``. La coloración
voraz por grado decreciente publica la cota por arriba; no es mínima.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import repo as R

MARCO = "post-rebase: se promete sobre las ramas ya rebasadas al tronco; pre-rebase da 40 falsos seguros de 105"


@dataclass(frozen=True)
class Lotes:
    ramas: tuple[str, ...]
    lotes: tuple[tuple[str, ...], ...]
    soportes: dict[str, tuple[str, ...]]
    pares_seguros: int
    pares_no_seguros: int
    cota_inferior: int

    @property
    def n(self) -> int:
        return len(self.ramas)

    @property
    def pares(self) -> int:
        return self.n * (self.n - 1) // 2

    @property
    def exacto(self) -> bool:
        """La voraz alcanza la cota inferior: el número de lotes es mínimo."""
        return len(self.lotes) == max(self.cota_inferior, 1) or len(self.lotes) < 2


def soportes(repo: str, tronco: str, refs: list[str]) -> dict[str, tuple[str, ...]]:
    """Archivos que cada rama toca por sí misma: ``diff(merge-base, rama)``.

    ``--no-renames`` a propósito: un rename aparece como borrado + alta, así que
    el soporte es **superconjunto** del real y la relación segura no promete de
    más.
    """
    salida: dict[str, tuple[str, ...]] = {}
    for ref in refs:
        base = R.base_de_rama(repo, tronco, ref)
        salida[ref] = tuple(R.rutas(repo, base, ref))
    return salida


def choques(sop: dict[str, tuple[str, ...]]) -> dict[str, set[str]]:
    """Grafo de choque: arista entre dos ramas que comparten al menos un archivo."""
    por_archivo: dict[str, list[str]] = {}
    for ref, rutas in sop.items():
        for ruta in rutas:
            por_archivo.setdefault(ruta, []).append(ref)
    grafo: dict[str, set[str]] = {ref: set() for ref in sop}
    for lista in por_archivo.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1 :]:
                if a != b:
                    grafo[a].add(b)
                    grafo[b].add(a)
    return grafo


def colorear(grafo: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Coloración voraz por grado decreciente: cada color es un lote seguro."""
    orden = sorted(grafo, key=lambda ref: (-len(grafo[ref]), ref))
    color: dict[str, int] = {}
    for ref in orden:
        usados = {color[v] for v in grafo[ref] if v in color}
        c = 0
        while c in usados:
            c += 1
        color[ref] = c
    grupos: dict[int, list[str]] = {}
    for ref, c in color.items():
        grupos.setdefault(c, []).append(ref)
    return tuple(tuple(sorted(v)) for _, v in sorted(grupos.items()))


def cota_inferior(sop: dict[str, tuple[str, ...]]) -> int:
    """Clique exacta y gratis: todas las ramas que tocan un mismo archivo."""
    cuenta: dict[str, int] = {}
    for rutas in sop.values():
        for ruta in rutas:
            cuenta[ruta] = cuenta.get(ruta, 0) + 1
    return max(cuenta.values(), default=0)


def lotes(repo: str, tronco: str, refs: list[str]) -> Lotes:
    sop = soportes(repo, tronco, refs)
    grafo = choques(sop)
    seguros = sum(len(v) for v in grafo.values()) // 2
    n = len(refs)
    return Lotes(
        ramas=tuple(refs),
        lotes=colorear(grafo),
        soportes=sop,
        pares_seguros=n * (n - 1) // 2 - seguros,
        pares_no_seguros=seguros,
        cota_inferior=cota_inferior(sop),
    )


def texto(l: Lotes, tronco: str, oid: str = "") -> str:
    cabecera = f"SUJETO · {l.n} ramas · tronco {tronco}"
    if oid:
        cabecera += f" ({oid})"
    lineas = [
        cabecera,
        f"LOTES · {len(l.lotes)} corrida(s) de CI · soporte por archivo, sin un merge",
        f"  pares {l.pares} · seguros {l.pares_seguros} (soporte disjunto) · "
        f"no seguros {l.pares_no_seguros} (comparten archivo)",
        f"  cota inferior del número de lotes: {l.cota_inferior} "
        "(ramas que tocan un mismo archivo)",
    ]
    for i, grupo in enumerate(l.lotes, start=1):
        lineas.append(f"  lote {i} ({len(grupo)}): {', '.join(grupo)}")
    if len(l.lotes) == 1:
        lineas.append("  un solo lote: todas las ramas son disjuntas dos a dos")
    elif l.exacto:
        lineas.append("  la voraz alcanza la cota inferior: el número de lotes es mínimo")
    else:
        lineas.append(
            f"  la voraz da {len(l.lotes)} y la cota inferior es {l.cota_inferior}: "
            "el mínimo está entre los dos (coloración exacta es NP-dura)"
        )
    lineas.append(f"  precondición: {MARCO}")
    lineas.append(
        "  cota declarada: dos ramas que tocan el mismo archivo en líneas distintas pueden"
        " mergear limpias y aquí cuentan como NO SEGURAS"
    )
    return "\n".join(lineas)
