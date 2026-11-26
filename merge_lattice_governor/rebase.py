"""Qué **acto** pide cada rama: rebasar o reordenar.

El plan de la matriz responde «¿en qué orden?». Ese orden no repara un conflicto cuya
contraparte es el tronco: 74 de los 80 conflictos del corpus del 26-Nov-2026 llevan una
rama atrasada como parte, y rebasar es el único acto que los toca.

Este módulo publica el acto **antes** de ejecutarlo, sin leer un solo blob:

    SIN_TRABAJO        la rama no tiene commits propios: ya está en el tronco, no pide aterrizaje.
    REBASAR_LIBRE      historia lineal y ninguna clase de identidad tocada por los dos lados.
    REBASAR_CON_MERGE_INTERNO  la rama guarda un merge: no se prueba nada, sólo se declara qué toca.
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

**El merge interno rompe el descarte, no la cota.** Con historia lineal, cada commit que el
replay reaplica tiene por base el `merge-base` de la pareja: si su ruta no está en las dos
listas netas, el cherry-pick es un no-op sobre esa ruta y no puede chocar. Con un merge
dentro de `base..ref` la base efectiva del replay es **anterior** al `merge-base`, y el
conflicto puede caer en una ruta que ninguna de las dos listas netas publica —porque la
resolución vivía en el árbol del merge, y un merge no se reaplica: se re-ejecuta—.
Medido el 26-Nov-2026 sobre tres sujetos (210 ramas con trabajo, rebase real): 23 ramas
`REBASAR_LIBRE`, **22 lineales y 22 limpias** (9 `~/primer`, 10 `psf/requests`, 4 el corpus);
la única con un merge interno (`psf/requests` `pr/7065`, merge `fe0853c6`, base
`6f66281a`) declaró LIBRE y paró en 3 conflictos. Su merge es **malvado**: los mismos
3 archivos chocan al fundir sus dos padres (`git merge-tree 5547eef 6f66281a`), y el
replay los reproduce porque no conserva la resolución. Por eso `REBASAR_LIBRE` exige ahora
historia lineal, y una rama con merge interno se publica como lo que es: no probada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import repo as R

AL_DIA = "AL_DIA"
SIN_TRABAJO = "SIN_TRABAJO"
REBASAR_LIBRE = "REBASAR_LIBRE"
REBASAR_CON_MERGE_INTERNO = "REBASAR_CON_MERGE_INTERNO"
REBASAR_CON_RIESGO = "REBASAR_CON_RIESGO"


@dataclass(frozen=True)
class Prescripcion:
    ref: str
    atras: int
    estado: str
    clases: tuple[str, ...] = ()
    riesgos: tuple[str, ...] = ()
    merges: int = 0

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


def _distancias(repo: str, tronco: str, ref: str) -> tuple[int, int]:
    """``(atrás, adelante)`` en **una** llamada: ``--left-right --count`` publica las dos.

    Dos ``rev-list --count`` cuestan 228 ms y una sola 57 ms (medido 25-Nov-2026 en un
    corpus de 12 000 commits); el número es el mismo campo a campo. Un reloj de pared
    no es un reloj de duración: las dos formas se comparan por su salida, no por su
    tiempo.
    """
    salida = R.exigir(
        R.git(repo, "rev-list", "--left-right", "--count", f"{tronco}...{ref}"),
        f"rev-list --count {tronco}...{ref}",
    ).split()
    if len(salida) < 2:
        raise R.ErrorGit(f"rev-list --left-right {tronco}...{ref}: salida sin dos cuentas")
    return int(salida[0]), int(salida[1])


def _tocados(
    repo: str, base: str, punta: str, clases: _Clases, *, copias: bool = False
) -> set[str]:
    """Rutas tocadas en ``base..punta`` y los renombrados declarados como aristas.

    ``--find-copies-harder`` sólo añade copias **desde fuentes no modificadas** —los
    renombrados ya los detecta ``-M``— y cuesta 32× por diff (medido 25-Nov-2026:
    3 283 ms frente a 101 ms). Sobre las 155 ramas vivas del corpus no cambió **ningún**
    veredicto (18 ``AL_DIA`` · 9 ``REBASAR_LIBRE`` · 128 ``REBASAR_CON_RIESGO`` idéntico)
    y, rebasando de verdad las 22 ramas cuyas clases se estrechan, no cubrió ni una de
    las 67 rutas que el acto puso en conflicto. Por eso no es el default: es ``copias``.
    """
    args = ["diff", "--name-status", "-M"] + (["--find-copies-harder"] if copias else [])
    salida = R.exigir(R.git(repo, *args, f"{base}..{punta}"), f"diff --name-status {base}..{punta}")
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


def _merges_internos(repo: str, base: str, ref: str) -> int:
    """Commits de merge en ``base..ref``: una llamada, y sólo en la rama que iba a ser libre.

    Es el único dato que separa «no hay ruta que chocar» de «no hay replay que reproducir».
    Se paga **después** de que las clases salgan disjuntas: en el corpus del 26-Nov-2026
    son 4 de 114 ramas, no 114.
    """
    salida = R.exigir(
        R.git(repo, "rev-list", "--merges", "--count", f"{base}..{ref}"),
        f"rev-list --merges --count {base}..{ref}",
    ).strip()
    try:
        return int(salida)
    except ValueError as exc:
        raise R.ErrorGit(f"rev-list --merges {base}..{ref}: {salida!r} no es una cuenta") from exc


def prescribir(
    repo: str, tronco: str, refs: list[str], *, copias: bool = False
) -> list[Prescripcion]:
    """Una prescripción por rama. Sólo lee: un ``rev-list`` y, si hay trabajo, dos diffs."""
    salida: list[Prescripcion] = []
    for ref in refs:
        atras, adelante = _distancias(repo, tronco, ref)
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
        de_rama = _tocados(repo, base, ref, clases, copias=copias)
        de_tronco = _tocados(repo, base, tronco, clases, copias=copias)
        comunes = {clases.raiz(p) for p in de_rama} & {clases.raiz(p) for p in de_tronco}
        if not comunes:
            # Disjuntas las clases, falta la otra mitad de la prueba: sin merge interno el
            # replay usa `base` como base de cada cherry-pick y una ruta que no está en
            # ninguna de las dos listas netas no puede chocar. Con merge, la base efectiva
            # es anterior y la resolución del merge no se reproduce.
            merges = _merges_internos(repo, base, ref)
            if merges:
                salida.append(
                    Prescripcion(
                        ref=ref,
                        atras=atras,
                        estado=REBASAR_CON_MERGE_INTERNO,
                        riesgos=tuple(sorted(de_rama)),
                        merges=merges,
                    )
                )
                continue
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
    cuenta = {
        AL_DIA: 0,
        SIN_TRABAJO: 0,
        REBASAR_LIBRE: 0,
        REBASAR_CON_MERGE_INTERNO: 0,
        REBASAR_CON_RIESGO: 0,
    }
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
    if cuenta[REBASAR_CON_MERGE_INTERNO]:
        lineas.append(
            f"  {REBASAR_CON_MERGE_INTERNO} {cuenta[REBASAR_CON_MERGE_INTERNO]}: la rama "
            "guarda un merge que el replay re-ejecuta, así que no se prueba nada"
        )
    for p in prescripciones:
        if p.estado in (AL_DIA, SIN_TRABAJO):
            continue
        if p.estado == REBASAR_LIBRE:
            lineas.append(f"  · {p.ref}  atrás {p.atras}  rebase sin riesgo textual medible")
            continue
        if p.estado == REBASAR_CON_MERGE_INTERNO:
            lineas.append(
                f"  · {p.ref}  atrás {p.atras}  rebase con {p.merges} merge(s) interno(s): "
                f"{len(p.riesgos)} archivo(s) propio(s) en juego"
            )
            for ruta in p.riesgos[:8]:
                lineas.append(f"      {ruta}")
            if len(p.riesgos) > 8:
                lineas.append(f"      … {len(p.riesgos) - 8} más")
            continue
        lineas.append(
            f"  · {p.ref}  atrás {p.atras}  rebase con {len(p.clases)} archivo(s) en juego"
        )
        for ruta in p.clases[:8]:
            lineas.append(f"      {ruta}")
        if len(p.clases) > 8:
            lineas.append(f"      … {len(p.clases) - 8} más")
    lineas.append(
        "  cota superior: 0 clases comunes e historia lineal ⇒ rebase sin conflicto textual; "
        "con clases, la lista es lo que puede chocar, no lo que chocará"
    )
    return lineas
