# Escalera de acoplamiento, 27-Nov-2026 — tres colas de PR ajenas

**La pregunta que contesta:** de las parejas de PRs abiertos de un repositorio, ¿cuántas son
**estructuralmente irreducibles** — es decir, cuántas van a chocar hagan lo que hagan con el
orden— y cuántas sólo necesitan turnarse?

**La respuesta corta, en tres repositorios públicos:** si dos PRs comparten **una** ruta chocan
entre el **10 % y el 31 %** de las veces. Si comparten **dos o más**, chocan entre el **55 % y el
78 %**. El orden de aterrizaje no toca ninguna de las dos cifras: una cola de merge decide *en qué
orden* entran las ramas, y esto mide *si pueden entrar de una pieza*. Para las parejas de la
segunda fila el diagnóstico es **partir el PR**, no reordenarlo.

## Qué se midió

Tres repositorios públicos, las **40 puntas de PR abiertas con número más bajo** de cada uno —las
más antiguas—, y **todas** sus parejas: 780 por sujeto, 2 340 en total.

| sujeto | puntas | parejas | motor |
|---|---|---|---|
| [`tiangolo/typer`](https://github.com/tiangolo/typer) | 40 de 46 abiertas | 780 | `merge_lattice_governor` v0.9.0 @ `6409669` |
| [`encode/httpx`](https://github.com/encode/httpx) | 40 de 100+ abiertas | 780 | idem |
| [`psf/black`](https://github.com/psf/black) | 40 de 73 abiertas | 780 | idem |

Por cada pareja `(a, b)` se publica:

* **`k`** — cuántas rutas tocan las dos ramas, medidas **contra `merge-base(a, b)`**, nunca contra
  el tronco. Medir contra el tronco confunde linaje compartido con colisión: una rama apilada sobre
  otra comparte decenas de rutas con `main` sin competir con nadie.
* el **veredicto** del merge de las dos puntas, calculado por
  [`merge_lattice_governor.parejas.pareja`](../../merge_lattice_governor/parejas.py) — el propio
  paquete, no una copia paralela del oráculo.

Cero escrituras en los tres sujetos: sólo `git` de lectura. Los tres quedaron con `git status`
limpio y el mismo `HEAD` con el que empezaron.

## Resultados

`P(rompe | k)` = fracción de parejas con ese `k` cuyo merge a tres bandas **no** es limpio. Entre
corchetes, intervalo de Wilson al 95 %.

| sujeto | parejas `k=0` | `k=1` | `k≥2` | `P(rompe \| k=1)` | `P(rompe \| k≥2)` | salto |
|---|---|---|---|---|---|---|
| `tiangolo/typer` | 144 | 330 | 306 | **0,3091** [0,2617 · 0,3609] | **0,5458** [0,4897 · 0,6006] | +23,7 pts |
| `encode/httpx` | 267 | 284 | 229 | **0,1972** [0,1551 · 0,2474] | **0,7817** [0,7237 · 0,8303] | +58,4 pts |
| `psf/black` | 3 | 88 | 689 | **0,1023** [0,0547 · 0,1831] | **0,7126** [0,6777 · 0,7452] | +61,0 pts |

**La columna `k=0` no es una medida, es un teorema.** Si las dos ramas no comparten ninguna ruta
contra su base común, no hay nada que fusionar y el merge es su unión por definición. Los 414 pares
de esa columna están limpios *por construcción* (414 = 144 + 267 + 3). Se publica para que se lea
como calibración del instrumento contra la definición, y para que nadie cite ese `0,00 %` como un
hallazgo sobre el mundo. En `psf/black` la celda tiene `n=3`: ese `0,0000` no mide nada — el IC95
llega a `0,5615`.

## Lo que se puede afirmar, y lo que no

1. **Una ruta compartida basta para romper, pero no suele** — 10 % a 31 % según el repositorio.
   Un único archivo en común es el régimen del *casi*: la mayoría de esas parejas se pueden
   turnar, y por eso una cola de merge sí les sirve.
2. **Dos rutas compartidas ya son mayoría de rotura** — 55 % a 78 %, y en los tres casos por encima
   del 50 %. La frontera no está donde la intuición la pone: no es «el PR toca mucho», es «el PR
   toca lo mismo que el otro en más de un archivo».
3. **La dirección del salto es la misma en 3 de 3 sujetos; la magnitud no.** El salto va de +23,7 a
   +61,0 puntos. Cualquier cifra única de «irreducibilidad» es una cifra de un repositorio, no de
   la ingeniería de software. Publicar el salto como constante sería inventar.
4. **`psf/black` tiene una cola estructuralmente irreducible**: 689 de 780 parejas (88,3 %) están en
   `k≥2` y el 64,1 % de la cola entera rompe. Ahí no hay orden que valga; hay que partir PRs.

## Dónde está el archivo, no la rama

Las rutas que más parejas comparten nombran el archivo que hay que partir. `parejas` / `en conflicto`:

| sujeto | ruta | parejas | en conflicto |
|---|---|---|---|
| `psf/black` | `CHANGES.md` | 686 | 462 |
| `psf/black` | `tests/test_black.py` | 464 | 333 |
| `psf/black` | `src/black/files.py` | 254 | 186 |
| `encode/httpx` | `httpx/_client.py` | 137 | 39 |
| `encode/httpx` | `CHANGELOG.md` | 114 | 109 |
| `encode/httpx` | `httpx/_transports/default.py` | 99 | 34 |
| `tiangolo/typer` | `typer/main.py` | 253 | 143 |
| `tiangolo/typer` | `typer/core.py` | 135 | 59 |
| `tiangolo/typer` | `tests/test_type_conversion.py` | 110 | 94 |
| `tiangolo/typer` | `typer/cli.py` | 91 | **0** |

Dos lecturas que no se ven en la tabla de arriba:

* El **changelog** es el hub más caro de los tres sujetos: 114 parejas de `httpx` comparten
  `CHANGELOG.md` y 109 de ellas chocan (95,6 %). Un archivo de una sola lista ordenada al final es
  el peor candidato posible a edición concurrente, y es el que todos los PRs tocan.
* Un hub **no siempre** rompe: 91 parejas de `typer` comparten `typer/cli.py` y **ninguna** choca.
  Merece una mirada, no una poda. La tabla publica los dos lados para que no se lea como una lista
  de culpables.

## Cómo se recalcula

Requiere `git`, [`gh`](https://cli.github.com) y Python 3.11+. Cero dependencias de terceros.

```bash
# 1. el sujeto, con sus puntas de PR abiertas como refs locales
REPO=tiangolo/typer; N=40; DIR=/tmp/cola
git clone --quiet https://github.com/$REPO "$DIR"
for n in $(gh pr list -R $REPO --state open --limit $N --json number --jq '.[].number'); do
  git -C "$DIR" fetch --quiet origin "pull/$n/head:refs/remotes/pr/$n"
done

# 2. la escalera (desde la raíz de este repositorio)
PYTHONPATH=. python3 evidencia/2026-11-27/escalera.py "$DIR" refs/remotes/pr/ --tope 40 --hubs 15
```

La salida estándar es una línea TSV por pareja: `a`, `b`, `k`, veredicto. Con `--hubs N` la salida
de error lleva además las N rutas compartidas por más parejas. Los tres TSV de esta corrida se
guardan en este directorio.

## Límites, declarados

* **`--tope 40` toma las de número más bajo, o sea las PRs abiertas más viejas** — no una muestra
  aleatoria. La más vieja es también la más divergente del tronco, así que estas cifras son una
  **cota alta** del acoplamiento de la cola, no su promedio. Un muestreo aleatorio con semilla
  declarada es la corrida siguiente.
* **`k` cuenta intersección de rutas, no de rangos de línea.** Dos ramas que editan zonas distintas
  del mismo archivo cuentan como acopladas aquí y no chocan en un merge real: la cifra sobreestima.
  El `k≥2` es, por tanto, una condición **suficiente para mirar**, no una promesa de conflicto.
* **No se ejecutan los drivers de `.gitattributes`.** En estos tres sujetos no hubo ninguno: las
  2 340 parejas se clasificaron `CONMUTA_LIMPIO` o `CONFLICTO_TEXTUAL`, cero `NO_MEDIDO`. En un
  repositorio con drivers, esa clase aparecería y se excluye del denominador.
* **No se lee el CI.** Un merge limpio de texto no dice nada sobre si la suite pasa.
* Las cifras son de `v0.9.0` @ `6409669`. La tercera poda de la [PR #6](https://github.com/alexisromtz-lab/merge-lattice-governor/pull/6) cambia el
  veredicto de los pares con **misma firma `(modo, blob)`** — no la escalera, que mide rutas
  compartidas — pero quien recorra esta evidencia después de ese merge debe citar el commit con el
  que la midió.
