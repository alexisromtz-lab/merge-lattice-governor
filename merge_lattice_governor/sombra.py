"""Colisión simbólica: dos lados declaran el mismo ordinal en la misma clase.

Python no avisa. El segundo ``def test_35_...`` del mismo ``class`` pisa al
primero en el diccionario de la clase, así que un merge textualmente limpio
deja el CI en verde **con un test menos**.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

_ORDINAL = re.compile(r"^test_?(\d+)")


@dataclass(frozen=True)
class Metodo:
    clase: str
    nombre: str
    linea: int

    @property
    def ordinal(self) -> int | None:
        encontrado = _ORDINAL.match(self.nombre)
        return int(encontrado.group(1)) if encontrado else None

    def rotulo(self) -> str:
        return f"{self.clase}.{self.nombre}" if self.clase else self.nombre


def _recorre(cuerpo: list[ast.stmt], prefijo: str, salida: list[Metodo]) -> None:
    for nodo in cuerpo:
        if isinstance(nodo, ast.ClassDef):
            _recorre(nodo.body, f"{prefijo}{nodo.name}.", salida)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if nodo.name.startswith("test"):
                metodo = Metodo(prefijo.rstrip("."), nodo.name, nodo.lineno)
                if metodo.ordinal is not None:
                    salida.append(metodo)


def metodos(fuente: str) -> list[Metodo]:
    """Métodos de test con ordinal, tolerando archivos que no compilan."""
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError):
        return []
    salida: list[Metodo] = []
    _recorre(arbol.body, "", salida)
    return salida


def colisiones(a: list[Metodo], b: list[Metodo]) -> list[tuple[Metodo, Metodo]]:
    """Pares con misma clase, mismo ordinal y distinto nombre.

    Mismo nombre no es colisión: es el mismo test en los dos lados y su
    diferencia es textual, que ya la mide ``merge-tree``.
    """
    indice: dict[tuple[str, int], list[Metodo]] = {}
    for metodo in a:
        indice.setdefault((metodo.clase, metodo.ordinal), []).append(metodo)
    encontradas: list[tuple[Metodo, Metodo]] = []
    for metodo_b in b:
        for metodo_a in indice.get((metodo_b.clase, metodo_b.ordinal), ()):
            if metodo_a.nombre != metodo_b.nombre:
                encontradas.append((metodo_a, metodo_b))
    return encontradas
