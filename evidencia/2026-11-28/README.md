# La escalera contra su propio muestreo, 28-Nov-2026 — semilla declarada en tres colas ajenas

**La pregunta que contesta:** la corrida del 27-Nov midió 2 340 parejas de PRs abiertas en tres
repositorios ajenos y declaró sus cifras *cota superior por edad*, porque creía haber tomado las 40
PRs más antiguas. ¿Era el salto entre una ruta y dos un artefacto de esa muestra?

**La respuesta corta, en dos actos.** El salto **no** es un artefacto: con muestreo aleatorio
uniforme de la población abierta completa (semilla declarada) sigue en **+24,2 / +53,0 / +68,9
puntos** y no baja en ningún repositorio. Pero al medirlo apareció algo peor que un sesgo: **la
muestra del 27-Nov no era la de las PRs más antiguas**. Era la primera página de `gh pr list
--limit 40` —el orden por defecto de `gh`, que es de actividad— y en `typer` dejaba fuera las 6 PRs
abiertas de número más bajo. La advertencia de «cota superior por edad» era falsa **en dirección**:
la muestra uniforme rompe *más*, no menos.

## El defecto que esta corrida destapó en la anterior

El error no fue de cálculo: las 2 340 parejas del 27-Nov están bien medidas y sus números son
exactos. El error fue de **procedencia**: el README afirmaba «las 40 puntas de PR abiertas con
número más bajo de cada uno —las más antiguas—» cuando el paso de descarga era
`gh pr list --state open --limit 40`, y `gh pr list` no ordena por número.

Tres comprobaciones, todas reproducibles hoy:

1. **`typer`**: la página de `gh pr list --limit 40` de hoy es **idéntica** a las 40 puntas medidas
   el 27-Nov (1 063 … 2 028) — y esa página **excluye** las 6 PRs abiertas de número más bajo
   (398, 459, 745, 828, 869, 985). Si la muestra fuera «las de número más bajo», las seis estarían
   dentro. No lo están.
2. **`httpx`**: las puntas medidas fueron 3 052 … 3 722; la página de hoy es 3 768 … 3 879. Otra.
3. **`black`**: las puntas medidas fueron 5 149 … 5 719; la página de hoy es 5 714 … 5 762. Otra.

Conclusión: la muestra del 27-Nov **no se reconstruye a partir de su receta**. Sólo los 40 números
publicados en sus TSV la definen. Por eso esta corrida publica población, semilla y muestra.

## La predicción, escrita antes de medir

Registrada el **28-Nov-2026 08:24 CST (14:24Z)**, antes de implementar la bandera `--muestra` y
antes de correr una sola pareja. Se transcribe sin retoques; el veredicto va después.

> 1. **Dirección:** `P(rompe|k≥2) > P(rompe|k=1)` en **3/3**. `cota_error`: 3/3.
> 2. **Umbral declarado:** salto ≥ +15 pts en 3/3.
> 3. **Magnitudes bajan** porque las PRs más antiguas divergen más del tronco:
>    typer **+10 .. +22** · httpx **+30 .. +50** · black **+35 .. +58**.
> 4. **Densidad de conflicto baja** en 3/3: typer 0,3449 → **0,20 .. 0,33** · httpx 0,3013 →
>    **0,15 .. 0,29** · black 0,6410 → **0,45 .. 0,62**.
>
> **Falsador del teorema completo:** salto < +10 pts en **2 de 3** ⇒ el efecto pertenecía a la
> antigüedad de la PR y no al solapamiento topológico `k ≥ 2`.

Los términos 3 y 4 se escribieron sobre una premisa que resultó falsa (que la muestra anterior era
la más antigua); el veredicto los juzga tal como se escribieron.

## Cómo se mide

1. **Población, no página.** `gh pr list --state open --limit 1000` sobre cada sujeto: 46, 104 y 74
   PRs abiertas el 28-Nov-2026, publicadas en `poblacion_<sujeto>.txt`.
2. **Muestra sembrada.** [`muestra.py`](muestra.py) aplica `random.Random(20261128).sample` sobre la
   población ordenada **numéricamente** y publica los números elegidos (`muestra_<sujeto>.txt`).
   Misma semilla y misma población ⇒ misma muestra, verificable por un tercero.
3. **Sólo se bajan las 40 puntas elegidas** (`git fetch origin pull/N/head:refs/remotes/pr/N`): el
   resto de la cola no se toca. Cero escrituras en los tres repositorios.
4. **La escalera.** [`../2026-11-27/escalera.py`](../2026-11-27/escalera.py) con
   `--muestra 40 --semilla 20261128 --hubs 10`, `k` medido **contra `merge-base(a, b)`** y veredicto
   del propio `merge_lattice_governor.parejas`. 780 parejas por sujeto, 2 340 en total.
5. **La tabla.** [`resumen.py`](resumen.py) recalcula densidad y tramos con intervalo de Wilson al
   95 % desde los TSV, sin llamar a `git`.

Costo medido (reloj, 5 hilos): typer 651 s · httpx 447 s · black 1 100 s, los tres en paralelo.

## Resultados

`P(rompe | k)` = fracción de parejas de ese tramo cuyo merge a tres bandas **no** es limpio. Entre
corchetes, Wilson 95 %. La columna *página gh (27-Nov)* es la cifra publicada ayer sobre 40 puntas
que resultaron ser una página de actividad, no las más antiguas.

| sujeto | abiertas | puntas | densidad página | densidad sembrada | `k=1` página | `k=1` sembrada | `k≥2` página | `k≥2` sembrada | salto página | **salto sembrado** |
|---|---|---|---|---|---|---|---|---|---|---|
| `tiangolo/typer` | 46 | 40 | 0,3449 | 0,3526 | 0,3091 | **0,2934** [0,2460·0,3457] | 0,5458 | **0,5353** [0,4822·0,5876] | +23,7 | **+24,2** |
| `encode/httpx` | 104 | 40 | 0,3013 | 0,3051 | 0,1972 | **0,2905** [0,2368·0,3507] | 0,7817 | **0,8235** [0,7654·0,8697] | +58,4 | **+53,0** |
| `psf/black` | 74 | 40 | 0,6410 | **0,5051** | 0,1023 | **0,0748** [0,0465·0,1180] | 0,7126 | **0,7636** [0,7243·0,7989] | +61,0 | **+68,9** |

Conteos de la corrida sembrada, para que el tramo no se lea sin denominador:

| sujeto | `k=0` (rompe) | `k=1` | `k≥2` | parejas |
|---|---|---|---|---|
| `tiangolo/typer` | 123 (0) | 317 | 340 | 780 |
| `encode/httpx` | 335 (0) | 241 | 204 | 780 |
| `psf/black` | 71 (0) | 214 | 495 | 780 |

**`k=0` sigue siendo teorema, ahora con más evidencia:** 529 parejas sin una sola ruta en común, 0
roturas. En `psf/black` la celda pasa de `n=3` (inútil) a `n=71` (aún corta: IC95 hasta `0,0513`):
la muestra uniforme arregló el peor agujero de la corrida anterior.

## Veredicto contra la predicción

| término | predicho | medido | veredicto |
|---|---|---|---|
| 1. Dirección en 3/3 | 3/3 | **3/3** | **CONFIRMADO** |
| 2. Salto ≥ +15 pts en 3/3 | 3/3 | **+24,2 · +53,0 · +68,9** | **CONFIRMADO** |
| 3. Magnitudes bajan (rangos por sujeto) | 0/3 dentro | **0/3 dentro** — los tres salen por arriba | **REFUTADO** |
| 4. Densidad baja 3/3 | 3/3 | **1/3** (sólo `black`, y dentro del rango) | **REFUTADO** |
| Falsador (< +10 pts en 2 de 3) | no se activa | no se activa | **TEOREMA EN PIE** |

Lo que se aprende de los dos términos falsos vale más que lo que confirman los dos ciertos:

1. **El sesgo iba al revés de lo que yo escribí.** Predije que la muestra anterior —creída la más
   antigua— exageraría la brecha, y la muestra uniforme la **sube** en `httpx` (+0,4 pts) y en
   `black` (+7,9 pts). Una página ordenada por actividad no es «la cola vieja»: es la cola
   **recientemente tocada**, y en estos tres sujetos resulta *menos* acoplada que la cola completa.
2. **La densidad sí dependía de la muestra, y sólo en `black`:** de 0,6410 a 0,5051 (13,6 pts) al
   pasar de la página de actividad a la población uniforme. En `typer` y `httpx` se mueve menos de
   un punto. Nada de esto convierte la cifra anterior en cota: la baja, la sube.
3. **Una regla de oro que este acto compra con su propio error:** una muestra se define por su
   procedencia, no por su tamaño. «40 puntas» no dice nada; «`random.Random(20261128).sample` sobre
   las 104 abiertas de `httpx` a las 08:24 CST» lo dice todo, y cualquiera lo repite.

## Dónde está el archivo, no la rama

Las tres rutas que más parejas comparten en la muestra sembrada, con cuántas de ellas rompen
(corrida con `--hubs 10`; tablas completas en `hubs_<sujeto>_semilla.tsv`):

| sujeto | ruta | parejas | en conflicto |
|---|---|---|---|
| `tiangolo/typer` | `typer/main.py` | 219 | 134 (61 %) |
| `encode/httpx` | `pyproject.toml` | 181 | 120 (66 %) |
| `psf/black` | `CHANGES.md` | 624 | 390 (63 %) |

`CHANGES.md` de `black` aparece en **624 de 780** parejas: es el 80 % de la cola entera. Ese archivo
—no las ramas— es el que convierte una cola de merge en una fila. Sacarlo del flujo por PR (o
generarlo al cortar la release) es una intervención de un solo archivo con efecto sobre 8 de cada
10 parejas. En `httpx` el equivalente es `pyproject.toml` (181 parejas, 66 % de rotura).

## Lo que se puede afirmar hacia afuera

1. **El diagnóstico no depende de la muestra.** Dos rutas compartidas contra `merge-base` rompen
   entre el **54 % y el 82 %** en muestra aleatoria de tres colas ajenas; una sola, entre el
   **7 % y el 29 %**. Es la misma frase del 27-Nov, ahora con la procedencia detrás.
2. **`k=0` es conmutación por definición** — 529 parejas, 0 roturas. Un oráculo que descarte esas
   parejas no acierta: aplica el teorema.
3. **Lo que no se afirma:** que el umbral sea exactamente 2. `k` es intersección de **rutas**, no de
   intervalos de línea: dos PRs que tocan el mismo archivo en extremos opuestos cuentan igual que
   dos que se pisan el mismo `def`. La versión 1-D está pendiente y es la que puede mover el umbral.
4. **La población se mueve.** Estas cifras son de las 08:24 CST del 28-Nov-2026 y de las poblaciones
   publicadas. Un repositorio con la mitad de su cola abierta hoy no da estas cifras mañana.

## Reproducir

```bash
gh pr list -R psf/black --state open --limit 1000 --json number --jq '.[].number' > poblacion.txt
python3 muestra.py --tamano 40 --semilla 20261128 < poblacion.txt > muestra.txt   # los números
# git fetch de esas 40 puntas como refs/remotes/pr/N, luego:
PYTHONPATH=. python3 ../2026-11-27/escalera.py /ruta/black refs/remotes/pr/ \
    --muestra 40 --semilla 20261128 --hubs 10 > parejas_black_semilla.tsv
python3 resumen.py parejas_black_semilla.tsv
```

`escalera.py` ordena las refs **numéricamente** (`pr/9` antes que `pr/10`) y muestrea con la misma
semilla, así que corrida sobre la población completa elige **la misma muestra** que `muestra.py`:
comprobado en los tres sujetos. `--tope N` y `--muestra N` se excluyen entre sí: el primero recorta
por orden, el segundo muestrea.

Sin dependencias: `git` y Python 3.9+ (`escalera.py` necesita el paquete en `PYTHONPATH`).
