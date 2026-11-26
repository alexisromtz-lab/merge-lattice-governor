"""Qué **acto** pide cada rama: rebasar o reordenar.

El plan de la matriz responde «¿en qué orden?». Ese orden no repara un conflicto cuya
contraparte es el tronco: 74 de los 80 conflictos del corpus del 26-Nov-2026 llevan una
rama atrasada como parte, y rebasar es el único acto que los toca.

Este módulo publica el acto **antes** de ejecutarlo, sin leer un solo blob:

    SIN_TRABAJO        la rama no tiene commits propios: ya está en el tronco, no pide aterrizaje.
    REBASAR_LIBRE      ninguna clase de identidad tocada por los dos lados.
    REBASAR_CON_RIESGO las clases comunes, para que el operador sepa qué archivos verá.
    AL_DIA             la rama ya contiene el tronco.

La identidad no es el nombre. Medido el 27-Nov-2026 sobre los PRs abiertos más viejos de
`psf/requests` (12 ramas): comparando **nombres**, 11 de 17 conflictos caían fuera de la
predicción —el tronco había renombrado `requests/models.py` → `src/requests/models.py` y
la rama tocó el nombre viejo—. Agrupando los nombres por clase de rename, 0 de 17 cayeron
fuera. En el corpus del 15 ramas, 0 de 10. Total medido: 27 ramas, 27 conflictos, 0 fuera.

Contra el acto real, el 27-Nov-2026: 28 ramas del corpus rebasadas de verdad
(`git rebase origin/main` con HEAD en la rama, no al revés). 14 `REBASAR_LIBRE` ⇒ 14
rebases limpios; 14 `REBASAR_CON_RIESGO` ⇒ 10 con conflicto (14 rutas) y 4 limpios;
**0 rutas fuera de las clases declaradas**. El acto confirma la cota.

Censo con la población declarada, 28-Nov-2026 (tronco `34ee1d2c8`, 275 refs locales):
**213 de las 275 ya están contenidas en el tronco** y no piden aterrizaje — sin
`SIN_TRABAJO` entraban como 213 `REBASAR_LIBRE` y el 72,5 % de la cola era un artefacto de
población—. Quedan **62 ramas vivas**, rebasadas de verdad con `git rebase --rebase-merges`:

| prescrito | n | rebase limpio | conflicto |
|---|---|---|---|
| `AL_DIA` | 7 | 7 | 0 |
| `REBASAR_LIBRE` | 2 | 2 | 0 |
| `REBASAR_CON_RIESGO` | 53 | 7 | 46 |

**9 de 9 veredictos «sin riesgo» respetados · 46 ramas en conflicto, 109 rutas, 1 fuera de
clase** (una `BITACORA/bloque-*.md` nueva). Instrumento: sin `--rebase-merges`, 3 ramas
`AL_DIA` con mergers del tronco en su historia se leían en conflicto sobre
`BITACORA/registro.jsonl` — el aplanado re-aplica lo que el tronco ya tiene.

Límite declarado: es cota **superior**, no igualdad. `orquestador-video` predijo 20 clases
y produjo 4 conflictos; `espejo-publicaciones` predijo 2 y produjo 0. Sirve para descartar
gratis (`REBASAR_LIBRE`), no para prometer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import repo as R

AL_DIA = "AL_DIA"
SIN_TRABAJO = "SIN_TRABAJO"
REBASAR_LIBRE = "REBASAR_LIBRE"
REBASAR_CON_RIESGO = "REBASAR_CON_RIESGO"


@dataclass(frozen=True)
class Prescripcion:
    ref: str
    atras: int
    estado: str
    clases: tuple[str, ...] = ()
    riesgos: tuple[str, ...] = ()

    @property
    def libre(self) -> bool:
        return self.estado == REBASAR_LIBRE


class _Clases:
    """Union-find sobre rutas: el rename es la arista de identidad."""

    def __init__(self) -> None:
        self._padre: dict[str, str] = {}

    def raiz(self, ruta: str) -> str:
        self._padre.setdefault(ruta, ruta)
        while self._padre[ruta] != ruta:
            self._padre[ruta] = self._padre[self._padre[ruta]]
            ruta = self._padre[ruta]
        return ruta

    def unir(self, a: str, b: str) -> None:
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self._padre[rb] = ra


def _tocados(repo: str, base: str, punta: str, clases: _Clases) -> set[str]:
    """Rutas tocadas en ``base..punta`` y los renombrados declarados como aristas."""
    salida = R.exigir(
        R.git(repo, "diff", "--name-status", "-M", "--find-copies-harder", f"{base}..{punta}"),
        f"diff --name-status {base}..{punta}",
    )
    tocadas: set[str] = set()
    for linea in salida.splitlines():
        campos = linea.split("\t")
        if len(campos) < 2:
            continue
        if campos[0][:1] in ("R", "C") and len(campos) >= 3:
            clases.unir(campos[1], campos[2])
            tocadas.update((campos[1], campos[2]))
        else:
            tocadas.add(campos[1])
    return tocadas


def prescribir(repo: str, tronco: str, refs: list[str]) -> list[Prescripcion]:
    """Una prescripción por rama. Sólo lee: dos rev-list y, si hay trabajo, dos diffs."""
    salida: list[Prescripcion] = []
    for ref in refs:
        atras = int(
            R.exigir(R.git(repo, "rev-list", "--count", f"{ref}..{tronco}"), f"rev-list {ref}..")
            .strip() or 0
        )
        adelante = int(
            R.exigir(R.git(repo, "rev-list", "--count", f"{tronco}..{ref}"), f"rev-list ..{ref}")
            .strip() or 0
        )
        if adelante == 0:
            # Contenida en el tronco: no hay nada que aterrizar. Llamarla REBASAR_LIBRE
            # infla el censo con ramas muertas que rebasan limpias por no tener commits.
            salida.append(Prescripcion(ref=ref, atras=atras, estado=SIN_TRABAJO))
            continue
        if atras == 0:
            salida.append(Prescripcion(ref=ref, atras=0, estado=AL_DIA))
            continue
        base = R.base_de_rama(repo, tronco, ref)
        clases = _Clases()
        de_rama = _tocados(repo, base, ref, clases)
        de_tronco = _tocados(repo, base, tronco, clases)
        comunes = {clases.raiz(p) for p in de_rama} & {clases.raiz(p) for p in de_tronco}
        if not comunes:
            salida.append(Prescripcion(ref=ref, atras=atras, estado=REBASAR_LIBRE))
            continue
        nombres: dict[str, set[str]] = {}
        for ruta in de_rama | de_tronco:
            raiz = clases.raiz(ruta)
            if raiz in comunes:
                nombres.setdefault(raiz, set()).add(ruta)
        salida.append(
            Prescripcion(
                ref=ref,
                atras=atras,
                estado=REBASAR_CON_RIESGO,
                clases=tuple(sorted({ruta for grupo in nombres.values() for ruta in grupo})),
                riesgos=tuple(sorted(p for p in de_rama if clases.raiz(p) in comunes)),
            )
        )
    return salida


def resumen(prescripciones: list[Prescripcion]) -> dict[str, int]:
    cuenta = {AL_DIA: 0, SIN_TRABAJO: 0, REBASAR_LIBRE: 0, REBASAR_CON_RIESGO: 0}
    for p in prescripciones:
        cuenta[p.estado] = cuenta.get(p.estado, 0) + 1
    return cuenta


def texto(prescripciones: list[Prescripcion]) -> list[str]:
    if not prescripciones:
        return []
    cuenta = resumen(prescripciones)
    lineas = [
        "PRESCRIPCIÓN · el acto que pide cada rama (clases de rename, lectura pura)",
        f"  {AL_DIA} {cuenta[AL_DIA]} · {REBASAR_LIBRE} {cuenta[REBASAR_LIBRE]} · "
        f"{REBASAR_CON_RIESGO} {cuenta[REBASAR_CON_RIESGO]}",
    ]
    if cuenta[SIN_TRABAJO]:
        lineas.append(
            f"  {SIN_TRABAJO} {cuenta[SIN_TRABAJO]}: sus commits ya están en el tronco, "
            "no piden aterrizaje ni rebase"
        )
    for p in prescripciones:
        if p.estado in (AL_DIA, SIN_TRABAJO):
            continue
        if p.estado == REBASAR_LIBRE:
            lineas.append(f"  · {p.ref}  atrás {p.atras}  rebase sin riesgo textual medible")
            continue
        lineas.append(
            f"  · {p.ref}  atrás {p.atras}  rebase con {len(p.clases)} archivo(s) en juego"
        )
        for ruta in p.clases[:8]:
            lineas.append(f"      {ruta}")
        if len(p.clases) > 8:
            lineas.append(f"      … {len(p.clases) - 8} más")
    lineas.append(
        "  cota superior: 0 clases comunes ⇒ rebase sin conflicto textual; con clases, "
        "la lista es lo que puede chocar, no lo que chocará"
    )
    return lineas
