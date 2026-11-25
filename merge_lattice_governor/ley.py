"""Ley del trinquete: cuánta holgura deja cada rama al aterrizar.

Las tres identidades son las que el corpus de platino-labs certifica sobre
``tests/test_ratio_arnes_producto.py``::

    techo    = BANDA_TECHO * producto        con producto = vivo + sim
    cubeta   = arnes - RATIO_LINEA_BASE * vivo
    dholgura = BANDA_TECHO * (dvivo + dsim) + RATIO_LINEA_BASE * dvivo - darnes

Un delta positivo no basta: lo que decide el orden es que la holgura acumulada
siga **estrictamente > 0 después de cada rama**, no sólo al final.
"""

from __future__ import annotations

from dataclasses import dataclass

RATIO_LINEA_BASE = 1.3698
BANDA_TECHO = 0.05

ARNES_PREFIJOS = ("tools/", "tests/", ".github/", "pre-write-gate/")
EXTENSIONES_CODIGO = (".py", ".sh", ".yml", ".yaml", ".toml", ".js", ".ts", ".mjs", ".cjs")
PREFIJO_SIMULACION = "sim/"

ARNES = "arnes"
VIVO = "vivo"
SIM = "sim"


def es_codigo(ruta: str) -> bool:
    return ruta.endswith(EXTENSIONES_CODIGO)


def clase_de(ruta: str) -> str | None:
    """Una ruta sin extensión de código no mueve la masa: devuelve None."""
    if not es_codigo(ruta):
        return None
    if ruta.startswith(ARNES_PREFIJOS):
        return ARNES
    if ruta.startswith(PREFIJO_SIMULACION):
        return SIM
    return VIVO


@dataclass(frozen=True)
class Masa:
    arnes: int = 0
    vivo: int = 0
    sim: int = 0

    @property
    def producto(self) -> int:
        return self.vivo + self.sim

    @property
    def neto(self) -> int:
        return self.arnes + self.vivo + self.sim

    def sumar(self, clase: str, neto: int) -> "Masa":
        if clase == ARNES:
            return Masa(self.arnes + neto, self.vivo, self.sim)
        if clase == VIVO:
            return Masa(self.arnes, self.vivo + neto, self.sim)
        if clase == SIM:
            return Masa(self.arnes, self.vivo, self.sim + neto)
        raise ValueError(f"clase desconocida: {clase!r}")

    def __add__(self, otra: "Masa") -> "Masa":
        return Masa(self.arnes + otra.arnes, self.vivo + otra.vivo, self.sim + otra.sim)

    def delta(self, ratio: float = RATIO_LINEA_BASE, banda: float = BANDA_TECHO) -> float:
        return round(banda * self.producto + ratio * self.vivo - self.arnes, 4)
