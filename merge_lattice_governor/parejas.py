"""Matriz de conmutatividad por parejas.

Dos ramas conmutan si su merge textual es limpio **y** no declaran el mismo
ordinal de test en la misma clase. La base se calcula por pareja: usar una base
global para N ramas de un mismo tronco inventa conflictos que no existen
(medido en el corpus: 76 rojos con base global, 1 con base por pareja).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from itertools import combinations

from . import repo as R
from .sombra import Metodo, colisiones, identicos, leer, metodos, nuevos

CONMUTA_LIMPIO = "CONMUTA_LIMPIO"
COLISION_SIMBOLICA_AST = "COLISION_SIMBOLICA_AST"
CONFLICTO_TEXTUAL = "CONFLICTO_TEXTUAL"
HISTORIAS_AJENAS = "HISTORIAS_AJENAS"
NO_MEDIDO = "NO_MEDIDO"

TEOREMA = "TEOREMA"
MEDIDO = "MEDIDO"
ATRIBUCION_TRONCO = "TRONCO"
ATRIBUCION_PAR = "PAR"

_PASO = ("text",)

_REGLAS: dict[tuple[str, str], dict[str, str]] = {}


def _reglas_de(repo: str, ref: str) -> dict[str, str]:
    clave = (repo, ref)
    if clave not in _REGLAS:
        _REGLAS[clave] = R.drivers(repo, [ref])
    return _REGLAS[clave]


@dataclass(frozen=True)
class Pareja:
    a: str
    b: str
    base: str | None
    textual: tuple[str, ...] = ()
    simbolica: tuple[str, ...] = ()
    ilegibles: tuple[str, ...] = ()
    identicos: tuple[str, ...] = ()
    driver: tuple[str, ...] = ()
    prefijo: tuple[str, ...] = ()
    decision: str = MEDIDO
    atribucion: str | None = None

    @property
    def driver_rutas(self) -> tuple[str, ...]:
        return tuple(e.split(" merge=")[0] for e in self.driver)

    @property
    def propias(self) -> tuple[str, ...]:
        """Conflictos de **nuestra** jurisdicción: los que el merge genérico sí mide."""
        ajenas = set(self.driver_rutas)
        return tuple(r for r in self.textual if r not in ajenas)

    @property
    def clase(self) -> str:
        if self.base is None:
            return HISTORIAS_AJENAS
        if self.propias:
            return CONFLICTO_TEXTUAL
        if self.simbolica:
            return COLISION_SIMBOLICA_AST
        if self.ilegibles:
            return NO_MEDIDO
        if self.driver:
            return NO_MEDIDO
        return CONMUTA_LIMPIO

    def describe(self) -> str:
        if self.clase == CONFLICTO_TEXTUAL:
            texto = f"{self.clase}: {', '.join(self.propias)}"
            if self.atribucion == ATRIBUCION_TRONCO:
                texto += " · TRONCO: esa ruta ya choca con el tronco en una de las dos ramas, rebasa primero"
            elif self.atribucion == ATRIBUCION_PAR:
                texto += " · PAR: el choque no viene del tronco, el orden no lo repara"
            if self.driver:
                texto += f" · además driver: {', '.join(self.driver)}"
            if self.prefijo:
                texto += f" · archivo/directorio: {', '.join(self.prefijo)}"
            return texto
        if self.clase == COLISION_SIMBOLICA_AST:
            return f"{self.clase}: {', '.join(self.simbolica)}"
        if self.clase == NO_MEDIDO:
            if self.driver:
                return (
                    f"{self.clase}: lo decide {', '.join(self.driver)} — el driver corre en el "
                    "merge real y aquí no se ejecuta: ni limpio ni rojo"
                )
            return f"{self.clase}: {', '.join(self.ilegibles)}"
        if self.identicos:
            return f"{self.clase} · {len(self.identicos)} duplicado(s) idéntico(s), ninguno se pierde"
        return self.clase


def _simbolicas(
    repo: str, a: str, b: str, base: str, comunes: list[str] | None = None
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(colisiones, ilegibles, duplicados idénticos) en las rutas .py de las dos ramas."""
    if comunes is None:
        comunes = sorted(
            {r for r in R.rutas(repo, base, a) if r.endswith(".py")}
            & {r for r in R.rutas(repo, base, b) if r.endswith(".py")}
        )
    hallazgos: list[str] = []
    ilegibles: list[str] = []
    iguales: list[str] = []
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
        for metodo_a, metodo_b in identicos(nuevos_a, nuevos_b):
            iguales.append(
                f"{_testigo(ruta, metodo_a, a)} vs {_testigo(ruta, metodo_b, b)}"
            )
    return tuple(hallazgos), tuple(ilegibles), tuple(iguales)


def _testigo(ruta: str, metodo: Metodo, ref: str) -> str:
    """`ruta:linea@ref Clase.metodo`: la línea es de esa rama, no del par."""
    corto = ref.rsplit("/", 1)[-1]
    return f"{ruta}:{metodo.linea}@{corto} {metodo.rotulo()}"


def pareja(repo: str, a: str, b: str, *, optimizar: bool = True, driver: bool = True) -> Pareja:
    """Un par, con su base **de pareja** y el veredicto de un merge a tres bandas.

    Teorema (soporte disjunto): con una sola base común, dos conjuntos de cambios
    que no tocan ningún archivo en común no pueden chocar — el merge es su unión.
    La condición es soporte disjunto **y** sin choque archivo/directorio: ``d``
    frente a ``d/x`` no comparte rutas y choca igual. Cuando se cumple, no hay
    merge que correr: la decisión es ``TEOREMA``. Es exacto, no un atajo:
    `--sin-optimizar` corre el merge igual y tiene que dar el mismo veredicto
    (test diferencial, incluido el caso archivo/directorio).

    ``driver=False`` ignora ``.gitattributes``: el veredicto es entonces el del
    merge genérico puro, que es una aproximación declarada, nunca la verdad.
    """
    base = R.base_de_par(repo, a, b)
    if base is None:
        return Pareja(a=a, b=b, base=None)
    soporte_a = {r for r in R.rutas(repo, base, a)}
    soporte_b = {r for r in R.rutas(repo, base, b)}
    comunes = sorted(soporte_a & soporte_b)
    prefijo = R.prefijos_en_choque(soporte_a, soporte_b)
    if optimizar and not comunes and not prefijo:
        return Pareja(a=a, b=b, base=base, decision=TEOREMA)
    simbolica, ilegibles, iguales = _simbolicas(
        repo, a, b, base, [r for r in comunes if r.endswith(".py")]
    )
    textual = R.rutas_en_conflicto(repo, a, b)
    decididas: tuple[str, ...] = ()
    if driver:
        reglas = {**_reglas_de(repo, a), **_reglas_de(repo, b)}
        decididas = tuple(
            f"{ruta} merge={nombre}"
            for ruta in comunes
            if (nombre := R.driver_de(reglas, ruta)) is not None and nombre not in _PASO
        )
    return Pareja(
        a=a,
        b=b,
        base=base,
        textual=textual,
        simbolica=simbolica,
        ilegibles=ilegibles,
        identicos=iguales,
        driver=decididas,
        prefijo=prefijo,
        decision=MEDIDO,
    )


def friccion(repo: str, tronco: str, ref: str) -> tuple[str, ...]:
    """Rutas en las que ``ref`` ya choca **con el tronco**: lo que arregla un rebase.

    Es el merge neutro ``merge-tree(tronco, ref)``, cuya base es el fork: el mismo
    conflicto que verá quien rebase. Una rama al día no mide: su soporte es vacío
    contra su propia base y el teorema la deja en cero sin tocar el ODB.
    """
    base = R.base_de_par(repo, tronco, ref)
    if base is None or base == R.resolver(repo, tronco):
        return ()
    return R.rutas_en_conflicto(repo, tronco, ref)


def fricciones(repo: str, tronco: str, refs: list[str]) -> dict[str, tuple[str, ...]]:
    return {ref: friccion(repo, tronco, ref) for ref in refs}


def anotar(parejas: list[Pareja], fric: dict[str, tuple[str, ...]]) -> list[Pareja]:
    """Atribuye cada conflicto: puede tener al tronco por contraparte.

    La atribución es una **explicación suficiente**, no una reparación probada: si
    todas las rutas del choque ya chocan con el tronco en alguna de las dos ramas,
    rebasar es el acto que hay que intentar primero; que el par siga rojo después
    lo convierte en ``PAR``.
    """
    salida: list[Pareja] = []
    for p in parejas:
        if p.clase != CONFLICTO_TEXTUAL:
            salida.append(p)
            continue
        explicadas = set(fric.get(p.a, ())) | set(fric.get(p.b, ()))
        clase = ATRIBUCION_TRONCO if set(p.propias) <= explicadas else ATRIBUCION_PAR
        salida.append(replace(p, atribucion=clase))
    return salida


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


def _preparar_hilos(repo: str, refs: list[str], driver: bool) -> None:
    """Deja hecho todo lo que escribe estado compartido, antes de abrir hilos.

    Dos cosas: el oráculo de ``merge-tree`` (un ``git init`` por sujeto) y la caché
    de ``.gitattributes``. Ambas son diccionarios de módulo que se llenan perezosos;
    rellenarlos dentro del pool es una carrera, no una optimización.
    """
    R.preparar(repo)
    if driver:
        for ref in refs:
            _reglas_de(repo, ref)


def matriz(repo: str, refs: list[str], *, optimizar: bool = True,
           driver: bool = True, jobs: int = 1) -> list[Pareja]:
    """Los ``N(N-1)/2`` pares. ``jobs > 1`` los reparte entre hilos.

    Cada par es **independiente y de sólo lectura** —su base es la de la pareja, no
    una global—, así que repartirlos no cambia un solo veredicto: el orden de la
    lista de salida es el de ``combinations``, no el de terminación. Un atajo que
    alterase la matriz no sería velocidad, sería otra medida.
    """
    pares = list(combinations(refs, 2))
    if jobs <= 1 or len(pares) < 2:
        return [
            pareja(repo, a, b, optimizar=optimizar, driver=driver) for a, b in pares
        ]
    _preparar_hilos(repo, refs, driver)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(
            pool.map(
                lambda par: pareja(repo, par[0], par[1], optimizar=optimizar, driver=driver),
                pares,
            )
        )


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


def decisiones(parejas: list[Pareja]) -> dict[str, int]:
    """Cuántos pares se decidieron sin merge (``TEOREMA``) y cuántos mergeando."""
    cuenta = {TEOREMA: 0, MEDIDO: 0}
    for p in parejas:
        cuenta[p.decision] += 1
    return cuenta


def atribucion(parejas: list[Pareja]) -> dict[str, int]:
    """De los pares en conflicto: cuántos se explican por el tronco y cuántos son del par."""
    cuenta = {ATRIBUCION_TRONCO: 0, ATRIBUCION_PAR: 0}
    for p in parejas:
        if p.atribucion:
            cuenta[p.atribucion] += 1
    return cuenta


def con_driver(parejas: list[Pareja]) -> list[Pareja]:
    """Pares donde un ``merge=<driver>`` decide el veredicto y no lo corremos."""
    return [p for p in parejas if p.driver]


def duplicados(parejas: list[Pareja]) -> dict[str, int]:
    """Duplicados idénticos: cuántos pares de ``def`` y en cuántas parejas.

    Van aparte de ``resumen`` porque la unidad es otra: ``resumen`` cuenta
    parejas de ramas y esto cuenta pares de definiciones. Sumarlos daría un
    total que no es de nadie.
    """
    con = [p for p in parejas if p.identicos]
    return {
        "duplicados_identicos": sum(len(p.identicos) for p in parejas),
        "parejas_con_duplicados_identicos": len(con),
    }


def incompatibles(parejas: list[Pareja]) -> list[Pareja]:
    return [p for p in parejas if p.clase not in (CONMUTA_LIMPIO,)]
