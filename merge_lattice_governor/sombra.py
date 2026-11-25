"""Colisión simbólica entre dos ramas: ordinal compartido o nombre compartido.

Hay dos defectos distintos y no se arreglan con la misma regla:

* **Mismo nombre en la misma clase.** El segundo ``def test_algo`` del mismo
  ``class`` pisa al primero en el diccionario de la clase: un merge
  textualmente limpio deja el CI en verde **con un test menos**. Medido el
  25-Nov-2026 en un repositorio de prueba: dos ramas que insertan
  ``def test_algo`` en rangos de línea distintos dan ``git merge-tree`` RC 0,
  cero marcas ``<<<<<<< .our``, el merge real entra limpio y el archivo acaba
  con 42 ``def`` y 41 nombres distintos. ``merge-tree`` no puede verlo porque
  no es un conflicto textual.

* **Mismo ordinal y nombre distinto en la misma clase.** Aquí no se pierde
  ningún test: los dos métodos sobreviven y corren. Se marca porque el número
  es el mecanismo con el que varios agentes se coordinan, y tras el merge dos
  autores creen ser el dueño del 35.
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
                salida.append(Metodo(prefijo.rstrip("."), nodo.name, nodo.lineno))


def metodos(fuente: str) -> list[Metodo]:
    """Métodos de test del archivo, tolerando lo que no compila.

    Incluye los que no llevan ordinal: ``def test_algo`` colisiona por nombre.
    """
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError):
        return []
    salida: list[Metodo] = []
    _recorre(arbol.body, "", salida)
    return salida


def nuevos(base: list[Metodo], ref: list[Metodo]) -> list[Metodo]:
    """Métodos de ``ref`` que no existen en ``base``.

    Un método heredado que las dos ramas comparten no es una colisión entre
    ellas: es la base. Sin este filtro el predicado dispara por ruido —medido
    en el corpus: 76 parejas aparentes, 1 real—.
    """
    heredados = {(m.clase, m.nombre) for m in base}
    return [m for m in ref if (m.clase, m.nombre) not in heredados]


def colisiones(
    a: list[Metodo],
    b: list[Metodo],
    *,
    incluir_mismo_nombre: bool = False,
) -> list[tuple[Metodo, Metodo]]:
    """Pares de la misma clase que colisionan.

    Regla del ordinal: mismo ordinal, nombre distinto.
    Regla del nombre (sólo con ``incluir_mismo_nombre``): mismo nombre exacto,
    que Python sí convierte en un test perdido.

    ``incluir_mismo_nombre`` nace apagado para no cambiar el contrato de quien
    ya llamaba a esta función; los llamadores que auditan una pareja de ramas
    deben encenderlo, porque es el caso que ``merge-tree`` no ve.
    """
    por_ordinal: dict[tuple[str, int], list[Metodo]] = {}
    por_nombre: dict[tuple[str, str], list[Metodo]] = {}
    for metodo in a:
        if metodo.ordinal is not None:
            por_ordinal.setdefault((metodo.clase, metodo.ordinal), []).append(metodo)
        por_nombre.setdefault((metodo.clase, metodo.nombre), []).append(metodo)
    encontradas: list[tuple[Metodo, Metodo]] = []
    vistos: set[tuple[int, int]] = set()

    def _anota(metodo_a: Metodo, metodo_b: Metodo) -> None:
        clave = (id(metodo_a), id(metodo_b))
        if metodo_a is metodo_b or clave in vistos:
            return
        vistos.add(clave)
        encontradas.append((metodo_a, metodo_b))

    for metodo_b in b:
        if metodo_b.ordinal is not None:
            for metodo_a in por_ordinal.get((metodo_b.clase, metodo_b.ordinal), ()):
                if metodo_a.nombre != metodo_b.nombre:
                    _anota(metodo_a, metodo_b)
        if incluir_mismo_nombre:
            for metodo_a in por_nombre.get((metodo_b.clase, metodo_b.nombre), ()):
                _anota(metodo_a, metodo_b)
    return encontradas
