"""Plan exacto del orden de aterrizaje bajo solvencia por prefijo.

El problema no es elegir un orden cualquiera: es que **cada prefijo** de la
secuencia mantenga la holgura > 0. Como la holgura final de un conjunto no
depende del orden (el delta es aditivo), basta una programación dinámica sobre
subconjuntos: ``factible[S]`` es cierto si algún orden de S deja todos sus
prefijos solventes, y la transición vuelve a comprobar el prefijo nuevo.

Encima de la solvencia hay una restricción que **no depende del orden**: dos
ramas con colisión simbólica no pueden aterrizar las dos, porque Python
sobrescribe un test y el merge entra limpio. Eso es un grafo de conflicto, no
una secuencia: el plan elige un conjunto independiente. Ordenar mejor no lo
arregla.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ley import BANDA_TECHO, RATIO_LINEA_BASE, Masa

MAXIMO_EXACTO = 18


@dataclass(frozen=True)
class Rama:
    nombre: str
    masa: Masa
    ref: str = ""
    base: str = ""

    @property
    def clave(self) -> str:
        return self.nombre or self.ref


@dataclass(frozen=True)
class Plan:
    orden: tuple[str, ...]
    trayectoria: tuple[float, ...]
    excluidas: tuple[str, ...]
    exacto: bool
    holgura_inicial: float

    @property
    def holgura_final(self) -> float:
        return self.trayectoria[-1] if self.trayectoria else self.holgura_inicial

    @property
    def integradas(self) -> int:
        return len(self.orden)

    @property
    def completo(self) -> bool:
        return not self.excluidas


def planificar(
    ramas: list[Rama],
    holgura_inicial: float,
    *,
    ratio: float = RATIO_LINEA_BASE,
    banda: float = BANDA_TECHO,
    maximo_exacto: int = MAXIMO_EXACTO,
    intocables: dict[int, int] | None = None,
    pesos: dict[str, float] | None = None,
) -> Plan:
    """``intocables[i]`` es la máscara de ramas que no pueden coexistir con ``i``.

    ``pesos`` declara la función objetivo: se maximiza el peso integrado y, a
    igual peso, el número de ramas y la holgura final. Sin ``pesos`` toda rama
    vale 1, así que el criterio se reduce a «cuántas caben».
    """
    if not ramas:
        return Plan((), (), (), True, holgura_inicial)

    deltas = [r.masa.delta(ratio, banda) for r in ramas]
    pesos = pesos or {}
    valor = [pesos.get(r.clave, 1.0) for r in ramas]
    n = len(ramas)
    choques = intocables or {}

    if n > maximo_exacto:
        return _voraz(ramas, deltas, holgura_inicial, choques, valor)

    total = 1 << n
    acumulado = [0.0] * total
    pesado = [0.0] * total
    for mask in range(1, total):
        bajo = mask & -mask
        i = bajo.bit_length() - 1
        resto = mask ^ bajo
        acumulado[mask] = acumulado[resto] + deltas[i]
        pesado[mask] = pesado[resto] + valor[i]

    factible = bytearray(total)
    factible[0] = 1
    for mask in range(total):
        if not factible[mask]:
            continue
        base = holgura_inicial + acumulado[mask]
        for i in range(n):
            bit = 1 << i
            if mask & bit:
                continue
            if mask & choques.get(i, 0):
                continue
            if base + deltas[i] > 0:
                factible[mask | bit] = 1

    mejor = 0
    clave = (-1.0, -1, float("-inf"))
    for mask in range(total):
        if not factible[mask]:
            continue
        candidata = (
            round(pesado[mask], 6),
            bin(mask).count("1"),
            round(holgura_inicial + acumulado[mask], 6),
        )
        if candidata > clave:
            mejor, clave = mask, candidata

    indices = tuple(i for i in range(n) if mejor >> i & 1)
    return _ensamblar(ramas, deltas, indices, holgura_inicial, exacto=True)


def _voraz(
    ramas: list[Rama],
    deltas: list[float],
    h0: float,
    choques: dict[int, int] | None = None,
    valor: list[float] | None = None,
) -> Plan:
    """Fuera de la cota exacta: gana el mayor peso entre los que caben, luego el delta."""
    choques = choques or {}
    valor = valor or [1.0] * len(ramas)
    pendientes = sorted(range(len(ramas)), key=lambda i: (-valor[i], -deltas[i], ramas[i].clave))
    elegidos: list[int] = []
    bloqueadas = 0
    holgura = h0
    while pendientes:
        for posicion, i in enumerate(pendientes):
            if bloqueadas & (1 << i):
                continue
            if holgura + deltas[i] > 0:
                elegidos.append(i)
                holgura += deltas[i]
                bloqueadas |= choques.get(i, 0)
                pendientes.pop(posicion)
                break
        else:
            break
    return _ensamblar(ramas, deltas, tuple(elegidos), h0, exacto=False)


def _ensamblar(ramas: list[Rama], deltas: list[float], indices: tuple[int, ...], h0: float, *, exacto: bool) -> Plan:
    """Dentro del conjunto elegido, el orden es el de delta descendente.

    Es el representante canónico: para un conjunto fijo, ordenar de mayor a menor
    delta maximiza *cada* prefijo a la vez (desigualdad de reordenamiento), así
    que maximiza el mínimo de la trayectoria y nunca es menos solvente que otro.
    """
    indices = sorted(indices, key=lambda i: (-deltas[i], ramas[i].clave))
    orden = tuple(ramas[i].clave for i in indices)
    trayectoria: list[float] = []
    holgura = h0
    for i in indices:
        holgura += deltas[i]
        if holgura <= 0:
            raise AssertionError(f"el orden canónico violó la solvencia en {ramas[i].clave}: {holgura}")
        trayectoria.append(round(holgura, 4))
    excluidas = tuple(r.clave for r in ramas if r.clave not in set(orden))
    return Plan(orden, tuple(trayectoria), excluidas, exacto, h0)
