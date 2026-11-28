# merge-lattice-governor

[![ci](https://github.com/alexisromtz-lab/merge-lattice-governor/actions/workflows/ci.yml/badge.svg)](https://github.com/alexisromtz-lab/merge-lattice-governor/actions/workflows/ci.yml) ![python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue) ![deps](https://img.shields.io/badge/dependencies-0-brightgreen) ![license](https://img.shields.io/badge/license-MIT-blue) [![doi](https://zenodo.org/badge/DOI/10.5281/zenodo.24548463.svg)](https://doi.org/10.5281/zenodo.24548463)

**El orden en que aterrizas tus ramas decide si el trinquete aguanta.** Este CLI mide las
masas de cada rama, comprueba qué parejas conmutan de verdad (texto **y** símbolos), y
resuelve por programación dinámica la secuencia exacta en la que **cada prefijo** sigue
siendo solvente.

Sin dependencias. Python ≥ 3.11. Cero escrituras en el repositorio que audita. La suite
tampoco arrastra ninguna: `python -m unittest discover -s tests -t .` corre en un intérprete
pelado —147 pruebas, medido el 28-Nov-2026 en un Python 3.12 sin PyYAML—.

```console
$ pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor@v0.9.0
$ merge-lattice-governor --base origin/main --holgura-inicial -1020.35 \
    --ref rama-pago --ref pr-402 --ref pr-401 --ref pr-403
```

Sin PyPI todavía, pero **sin clonar**: el wheel viaja como artefacto inmutable del release,
así que un CI lo instala en una línea y sin compilar.

```console
$ uvx --from https://github.com/alexisromtz-lab/merge-lattice-governor/releases/download/v0.9.0/merge_lattice_governor-0.9.0-py3-none-any.whl merge-lattice-governor --version
$ pip install https://github.com/alexisromtz-lab/merge-lattice-governor/releases/download/v0.9.0/merge_lattice_governor-0.9.0-py3-none-any.whl
```

`uvx` exige el nombre PEP 427 completo (`nombre-versión-py3-none-any.whl`): un nombre
abreviado se rechaza antes de instalar.

### Como hook de `pre-commit`

```yaml
repos:
  - repo: https://github.com/alexisromtz-lab/merge-lattice-governor
    rev: v0.9.0
    hooks:
      - id: merge-lattice-governor
        args: ["--base", "origin/main", "--holgura-inicial", "46.62",
               "--ref", "origin/pr-402", "--ref", "origin/pr-401"]
```

```console
$ pre-commit run merge-lattice-governor --hook-stage manual
```

Igual que su herramienta hermana, es un hook `manual`: el plan necesita la holgura
inicial y la lista de ramas, y esas dos cosas las declara quien opera la cola, no el
`git commit`.

### Como acción de GitHub (`uses:`)

```yaml
jobs:
  aterrizaje:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # el predicado exacto necesita el historial
      - uses: alexisromtz-lab/merge-lattice-governor@v0.9.0
        with:
          holgura-inicial: "46.62"          # obligatoria: la ley de masa es tuya
          refs: "origin/pr-402 origin/pr-401 origin/pr-403"
          salida-json: artefactos/plan.json
```

El **RC del gobernador es el RC del paso**: un plan insolvente tumba el check en vez de
publicarse como verde. Entradas: `holgura-inicial` (obligatoria cuando hay plan) · `refs` ·
`base` (por defecto `origin/main`) · `repo` (vacío = el workspace) · `ratio` · `banda` ·
`lotes` · `argumentos` · `salida-json`. Salida `rc` para consumirla en pasos posteriores.

Con `lotes: "true"` la acción no pide cubeta y publica las **corridas de CI sin choque
posible** —el ahorro de minutos es el producto—:

```yaml
      - uses: alexisromtz-lab/merge-lattice-governor@v0.9.0
        with:
          lotes: "true"
          refs: "origin/pr-402 origin/pr-401 origin/pr-403 origin/pr-405"
          salida-json: artefactos/lotes.json
```

Se recomienda fijar la etiqueta exacta (`@v0.9.0`). Este repositorio **no** mantiene una
etiqueta móvil `@v0`: una referencia mutable que promete lo que dice una versión fija es la
misma clase de defecto que un plan sin su marco —no se puede citar lo que cambia solo—.

Con `argumentos: "--prescribir"` la acción no ordena nada: publica **el acto que pide cada
rama** (`AL_DIA` · `REBASAR_LIBRE` · `REBASAR_CON_MERGE_INTERNO` · `REBASAR_CON_RIESGO` · `SIN_TRABAJO`), que es lo que se
consulta antes de decidir si el plan es siquiera el problema:

```yaml
      - uses: alexisromtz-lab/merge-lattice-governor@v0.9.0
        with:
          refs: "origin/pr-402 origin/pr-401 origin/pr-403"
          argumentos: "--prescribir"
          salida-json: artefactos/prescripcion.json
```

---

## El problema

Con 8–30 PRs abiertos, un merge queue ordena por llegada. Nadie te dice que la rama que
llegó tercera consume el presupuesto que la séptima necesitaba para no romper el trinquete,
ni que dos ramas que Git fusiona «limpias» declaran el mismo `test_35` en la misma clase y
Python resuelve el empate **borrando un test en silencio**.

Cuatro puntos ciegos, los cuatro medidos:

| Punto ciego | Qué se pierde | Cómo lo mide esta herramienta |
|---|---|---|
| El orden no se mira | un prefijo insolvente aunque el final sea verde | DP exacto sobre subconjuntos: `factible[S]` sólo si **algún** orden de `S` deja todos sus prefijos `> 0` |
| La base es global | conflictos inventados al comparar N ramas de un mismo tronco | `git merge-base` **por pareja** para conflicto y **por rama** para masa |
| El merge «limpio» puede estar gobernado | 13 verdes falsos en 105 pares: un `merge=<driver>` no deja marcas | `merge-tree --write-tree` sobre un ODB desechable + `NO_MEDIDO` cuando decide un driver |
| El merge textual no ve identificadores | shadowing silencioso de métodos de test | AST de ambos lados: misma clase, mismo ordinal, distinto nombre |

## La ley

Tres identidades, las mismas que certifica el corpus de `platino-labs`:

```
techo    = BANDA_TECHO · producto            producto = vivo + sim
cubeta   = arnés − RATIO_LINEA_BASE · vivo
Δholgura = BANDA_TECHO·(Δvivo+Δsim) + RATIO_LINEA_BASE·Δvivo − Δarnés
```

Con `BANDA_TECHO = 0.05`, `RATIO_LINEA_BASE = 1.3698`, y la clasificación por ruta:
`tools/ tests/ .github/ pre-write-gate/` → **arnés**; `sim/` → **simulación**; el resto del
código → **producto vivo**; un archivo sin extensión de código (`.md`, `.json`, `.html`) no
mueve la masa.

Una rama con `Δholgura` negativo no es una rama mala: es una rama que **necesita que otra
abra la banda antes**. Eso es exactamente lo que ordena el planificador.

## Errata: 13 verdes falsos, y el predicado que los cierra

La 0.2.x decidía el conflicto textual buscando las marcas `<<<<<<< .our` en la salida de
`git merge-tree <base> <a> <b>`. Ese predicado **miente en silencio** cuando una ruta está
gobernada por un `merge=<driver>`: el driver se ejecuta dentro de `merge-tree`, no deja
marcas, y la ruta se lee limpia aunque el merge real se detenga o aborte.

Medido el 26-Nov-2026 sobre las 105 parejas de la cola de 15 PRs, contra un oráculo
independiente (`git merge-tree --write-tree`, que sí ejecuta el driver):

| | 0.2.x (marcas) | 0.3.0 (exacto) |
|---|---|---|
| `CONFLICTO_TEXTUAL` | 61 | **74** |
| `CONMUTA_LIMPIO` | 44 | **26** |
| `NO_MEDIDO` | 0 | **18** |
| discrepancias vs oráculo | **13 / 105** | **0 / 105** |

Las 13 caían todas en dos rutas: `INVENTARIO_INSTRUMENTOS.md` y
`tests/test_indice_privado.py`, gobernadas por `merge=platino-derivado` — un driver que
**para diseño**. El diferencial completo (105 parejas, 116 s, 0 discrepancias) se corrió una
vez por fuera de la suite; lo que la suite fija en `tests/test_teorema.py::DiferencialCLI` es
que el atajo y el merge dan el mismo veredicto en los casos sintéticos, para que la
equivalencia no dependa de una corrida que ya pasó.

Y hay una clase más que ninguna marca puede ver: **el driver corre aunque el merge
genérico sea limpio**. Cinco parejas de la cola cambian las dos lados una ruta gobernada sin
ninguna marca de conflicto; el merge real igual invoca el driver. Regla adoptada: si los dos
lados cambian una ruta con `merge=<nombre>` y `nombre != text`, el par es **`NO_MEDIDO`** —
el driver decide en el merge real y este instrumento no lo ejecuta. `--ignorar-driver` es la
aproximación declarada, no el default.

**Cómo se mide el oráculo sin escribir en el repositorio auditado:** un `git init` no-bare
en `tempfile.mkdtemp()` cuyo `.git/objects/info/alternates` apunta al ODB del sujeto. El
`merge-tree --write-tree` escribe sus objetos en ese ODB desechable, no en el del sujeto, y
el árbol se borra al salir. Dos trampas medidas y cerradas: `merge-tree` con un *nombre* de
ref que no existe devuelve **RC 1 y stdout vacío** —indistinguible de un conflicto si sólo
se mira el código—, así que las refs se resuelven a OID antes; y `-c core.quotepath=false`
va **antes** del subcomando.

## Teorema: soporte disjunto, y por qué el atajo es exacto

Con **una sola base común**, dos conjuntos de cambios con soporte de archivos disjunto no
pueden chocar: el merge es su unión. No es una regularidad empírica, es un teorema, y basta
para no mergear una cuarta parte de la matriz.

Medido sobre la cola: **25 de 105** parejas tienen soporte disjunto, **25 conmutan**. Sin
una sola violación. El atajo se puede apagar con `--sin-optimizar`, y el diferencial
correspondiente (`clase` y `textual` idénticos en 105/105) es lo que convierte el atajo en
un teorema medido en vez de una opinión: en la corrida completa, `DECISIÓN` publica
`TEOREMA 25 · MEDIDO 80` y las 105 parejas dan el mismo veredicto por los dos caminos.

Corolario que el teorema **no** autoriza: soporte común no implica conflicto. En la misma
cola, 26 parejas limpias incluyen parejas que tocan el mismo archivo en regiones distintas.

### El borde: archivo frente a directorio

«Soporte disjunto» no basta si se lee como igualdad de rutas. Un archivo `dw` en una rama y
un archivo `dw/inner.txt` en la otra **no comparten ninguna ruta** y el merge choca igual:
las dos ramas quieren nombres incompatibles para el mismo prefijo. Medido el 28-Nov-2026 en
un repositorio sintético: el atajo devolvía `TEOREMA` (conmutan) y `git merge-tree` devolvía
RC 1 con `CONFLICT (file/directory)` y `dw` desplazado a `dw~<oid>`.

Desde 0.9.0 el atajo exige soporte disjunto **y** ausencia de choque de prefijo, y el
veredicto publica `prefijo[]` cuando la pareja se midió por esa razón. El mismo predicado
gobierna `--lotes`: una arista entre `d` y `d/x` dentro de un lote prometido sería un lote
que no compila. Coste medido en la cola real: `0` parejas con choque de prefijo sobre las
190 de la muestra, matriz idéntica.

### La segunda poda: misma firma `(modo, blob)`

Soporte común tampoco implica conflicto cuando las dos ramas piden **el mismo estado**: si en
cada ruta común quedan los mismos bytes y el mismo modo, el merge es `x ⊔ x = x` y no hay
nada que correr. La firma es el par `(modo, blob)`, no el blob: dos ramas que dejan los mismos
bytes pero una lo marca ejecutable (`100755` frente a `100644`, o un symlink `120000`) chocan
con `CONFLICT (add/add)`. Medido el 26-Nov-2026 en repositorio sintético: mismo blob y mismo
modo ⇒ merge limpio en las dos órdenes, con una sola copia del archivo; mismo blob y modo
distinto ⇒ RC 1 en las dos órdenes.

Desde 0.10.0 el atajo aplica también cuando todas las rutas comunes tienen la misma firma, y
el veredicto publica `idempotentes[]`. El diferencial `--sin-optimizar` sigue siendo la
prueba: para la pareja idempotente devuelve `MEDIDO`, la misma `clase` y `textual` vacío.

Masa medida en la cola real (las 20 ramas más recientes de `platino-labs`, 190 parejas,
26-Nov-2026): `IDEMPOTENTES 28 ruta(s) en 4 pareja(s)`, `prefijo` vacío en 190/190. La poda
**no movió un solo veredicto** en esa cola —las cuatro parejas chocan en otras rutas— y no
tiene por qué moverlo: lo que quita son 28 rutas que ya no hay que reconciliar a mano, porque
su merge es `x ⊔ x`. El caso en que sí decide es la pareja que sólo toca firmas idénticas: ahí
devuelve `TEOREMA` y el diferencial lo confirma con un merge limpio.

Reproducción: `git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/heads |
head -20` sobre `platino-labs`, con `--sin-plan --json --jobs 8`. La muestra se mueve con el
reloj: la cifra vale `@ 26-Nov-2026`, no como constante.

Y el marco importa: el teorema vale contra el **merge-base de la pareja**, no contra el
tronco. Medido el 25-Nov-2026 en `psf/requests`, 4 de 7 parejas conflictivas tenían soporte
disjunto *medido contra el tronco* y aun así chocaban — porque lo que chocaba era el lado
fresco contra los cambios que el tronco hizo desde la bifurcación del otro (`pr-7388`, 57
commits atrás). Ahí el soporte no es propiedad de la rama: es propiedad del marco.

## Atribución: el conflicto puede tener al tronco por contraparte

Una pareja que choca no siempre se repara reordenando. Si cada ruta en conflicto ya choca
entre una de las ramas y el tronco —`merge-tree(tronco, ref)`, cuya base es el punto de
bifurcación, que es exactamente el conflicto que encuentra un `git rebase`— la contraparte
es el **tronco**: reordenar no lo toca y el acto único es rebasar.

Medido en la cola: **57 pares atribuidos al tronco · 4 al par**. La fricción por rama
(`ramas[].friccion_con_tronco`) se publica aparte, porque es un hecho de la rama y no de la
pareja: **0 rutas en 8 de las 15 ramas** y **1–6 en las otras 7**, con
`orquestador-video-20261110` a la cabeza (6 rutas: `.gitignore`,
`.github/copilot-instructions.md`, dos tests y `tools/hooks/pre_push_map.json`).

## Prescripción: el acto, antes de ejecutarlo (`--prescribir`)

La atribución dice *cuándo* el acto es rebasar. `--prescribir` lo publica rama a rama y sin
leer un solo blob —dos `git diff` y un `rev-list` por rama—:

| estado | significado |
|---|---|
| `SIN_TRABAJO` | **0 commits propios**: la rama ya está en el tronco, no pide aterrizaje ni rebase |
| `AL_DIA` | la rama contiene el tronco y tiene trabajo propio: no pide acto |
| `REBASAR_LIBRE` | **0 clases de identidad** tocadas por los dos lados **e historia lineal**: rebase sin conflicto textual |
| `REBASAR_CON_MERGE_INTERNO` | clases disjuntas pero **la rama guarda un merge**: el replay lo re-ejecuta y la resolución no se reproduce. No se prueba nada: `clases_comunes` sale vacía y `riesgos` publica lo que la rama toca |
| `REBASAR_CON_RIESGO` | las clases comunes, para que el operador sepa qué archivos verá |

Y la ley que lo sostiene, medida el 27-Nov-2026:

> **La identidad de una ruta no es su nombre.** Comparando **nombres**, 11 de 17 conflictos
> de rebase quedaban fuera de la predicción en los PRs abiertos más viejos de `psf/requests`:
> el tronco había renombrado `requests/models.py` → `src/requests/models.py` y la rama tocó
> el nombre viejo, así que los conjuntos de nombres salían disjuntos y el par se leía «libre».
> Agrupando los nombres por clase de rename (`-M`, union-find): **0 de 17 fuera**. Sobre la
> cola del corpus: **0 de 10**. Total: **27 ramas, 27 conflictos, 0 fuera.**

Es **cota superior, no igualdad**: `orquestador-video-20261110` predijo 20 archivos y chocó
en 4; `espejo-publicaciones-20261111` predijo 2 y chocó en 0. Sirve para descartar gratis
—un `REBASAR_LIBRE` está probado sin merge-tree—, no para prometer.

**Corrección v0.8.0 — el descarte pedía una condición más.** Disjuntas las clases, la prueba
se apoyaba en que «no hay commit que reproducir ⇒ no hay ruta que ver». Falso para una rama
con un merge dentro: la base efectiva del replay es **anterior** al `merge-base` y el
conflicto puede caer en una ruta que ninguna de las dos listas netas publica como común.
Medido el 26-Nov-2026 sobre tres sujetos (210 ramas con trabajo, rebase real): de **23
`REBASAR_LIBRE`, las 22 con historia lineal rebasaron limpias y la única con merge interno
—`psf/requests` `pr/7065`, merge `fe0853c6`— paró en 3 conflictos**. Su merge es *malvado*:
`git merge-tree` de sus propios padres choca en los mismos 3 archivos. Por eso `REBASAR_LIBRE`
exige ahora `git rev-list --merges --count base..ref == 0`, y esa rama se publica como
`REBASAR_CON_MERGE_INTERNO`. Cuesta **una llamada más, sólo en la rama que iba a ser libre**.
El kit que recalcula estas cifras —sondas, TSV de cobertura y las 23 ramas con su veredicto—
está en [`evidencia/2026-11-26/`](evidencia/2026-11-26/README.md), sin red y sin ZIP.

**Contra el acto real**, no contra un oráculo: 28 ramas del corpus rebasadas de verdad
(`git rebase origin/main` con HEAD en la rama) el 27-Nov-2026. **14 `REBASAR_LIBRE` ⇒ 14
rebases limpios**; 14 `REBASAR_CON_RIESGO` ⇒ **10 con conflicto** (14 rutas) y 4 limpios;
**0 rutas fuera de las clases declaradas**. Un `REBASAR_LIBRE` no es una apuesta.

Sobre la cola de 15 PRs del 27-Nov-2026 (tronco `34ee1d2c8`): **7 `AL_DIA` · 1
`REBASAR_LIBRE`** (`agrupar-lectores`, 3 commits atrás) · **7 `REBASAR_CON_RIESGO`**
(`orquestador-video` con 20 archivos en juego, el resto 1–2). No cambia el RC: es el acto,
no el veredicto.

```console
$ merge-lattice-governor --base origin/main --prescribir --sin-plan --ref origen/rama-a --json
```

La salida de texto publica `SIN_TRABAJO` en **una línea agregada** y saca esas refs del
cuerpo: una rama que ya está en el tronco no es una rama de la cola, y listarla rama a rama
era lo que hacía parecer que la cola tenía 275 miembros.

```console
$ merge-lattice-governor --base origin/main --prescribir
PRESCRIPCIÓN · el acto que pide cada rama (clases de rename, lectura pura)
  AL_DIA 7 · REBASAR_LIBRE 2 · REBASAR_CON_RIESGO 53
  SIN_TRABAJO 213: sus commits ya están en el tronco, no piden aterrizaje ni rebase
  REBASAR_CON_MERGE_INTERNO 1: la rama guarda un merge que el replay re-ejecuta,
  así que no se prueba nada
  · <ref>  atrás <n>  rebase sin riesgo textual medible
  · <ref>  atrás <n>  rebase con <m> merge(s) interno(s): <k> archivo(s) propio(s) en juego
      <ruta que la rama toca>
  · <ref>  atrás <n>  rebase con <k> archivo(s) en juego
      <ruta que puede chocar>
      … N más
  cota superior: 0 clases comunes e historia lineal ⇒ rebase sin conflicto textual;
  con clases, la lista es lo que puede chocar, no lo que chocará
```

El agregado y la línea `SIN_TRABAJO` son los medidos sobre la cola del 28-Nov-2026; las filas
por rama van con marcadores porque son 62.

### La copia hardera cuesta 32× y no compró ni una ruta (`--copias`)

`--find-copies-harder` sólo añade copias **desde fuentes que el diff no modificó** —los
renombrados ya los detecta `-M`—. Medido el 25-Nov-2026 sobre las **155 ramas vivas** del
corpus (12 000 commits), con el mismo binario y la misma caché:

| | `--prescribir` completo | por diff |
|---|---|---|
| sin el flag (**default**) | **40 s** | 101 ms |
| con `--copias` | **209 s** | 3 283 ms |

**5,2× de reloj para 0 veredictos.** Los tres estados salieron idénticos —`AL_DIA 18 ·
REBASAR_LIBRE 9 · REBASAR_CON_RIESGO 128`— y el cuerpo de la salida con `--copias` reproduce
**byte a byte** el de la versión anterior: el flag no cambió ni un renglón del censo. Lo que
sí cambia es **la lista de clases** de 22 de las 137 ramas: se estrecha, porque una copia que
sólo el flag veía entraba en la clase de identidad como si fuera una arista.

¿Y ese estrechamiento pierde cobertura? Se rebasaron **de verdad** las 22 ramas
(`git rebase --rebase-merges` sobre el tronco medido, en un clon `--shared`): las 22
conflictúan, produciendo **67 rutas** en conflicto.

- dentro de la cota ancha: **3** rutas
- dentro de la cota estrecha: **3** rutas — las mismas tres
- rutas que **sólo** la cota ancha cubría: **0**

De ahí sale una ley que la tabla anterior no podía ver:

> **La prescripción es función del diff neto `base..ref`; el acto re-aplica el grafo de
> commits.** Las tres rutas que la cota no ve son exactamente las rutas que el diff neto
> **no puede ver** y el replay **sí**: dos archivos creados y borrados dentro de la rama
> (aparecen en `git log --name-only`, no en `git diff --name-only`), y uno modificado sólo
> del lado de la rama, cuyo conflicto vive dentro de un merge que el replay re-ejecuta.

No es un defecto del flag: es el borde donde la cota y el acto dejan de hablar del mismo
objeto. Un `REBASAR_LIBRE` sigue probado; una lista de `riesgos` sigue siendo lo que **puede**
chocar.

El mismo día, dos `git rev-list --count` se sustituyeron por uno solo
(`--left-right --count`, que publica el par `(atrás, adelante)`): **57 ms frente a 228 ms**,
mismo número campo a campo.

```console
$ merge-lattice-governor --base origin/main --prescribir            # 40 s, 155 ramas
$ merge-lattice-governor --base origin/main --prescribir --copias   # 209 s, la cota ancha
```

### La matriz por parejas es O(N²), y por eso trae hilos (`--jobs`)

`--prescribir` es lineal en llamadas a git: **7,27 s** sobre 62 refs (28-Nov-2026). La
**matriz por parejas** no: un merge de prueba por par, ≈0,63 s cada uno, medido en un clon
del corpus con 190 parejas (20 refs) en **114,6 s** de serie. Extrapolado a 62 refs (1 891
parejas) son ≈20 min: la cifra que hace inútil la herramienta en un CI ajeno.

Lo que se puede abaratar sin tocar el teorema es el factor constante. Cada par es
independiente y de sólo lectura, así que la matriz corre en hilos: **114,6 s → 46,4 s
(`--jobs 8`) y 43,8 s (`--jobs 16`)** sobre las mismas 190 parejas, con las 190 filas
idénticas campo a campo (`clase`, `textual`, `simbolica`, `decision`). Más de 8 hilos no
mejora: el coste es arrancar procesos, no calcular.

Dos precauciones que el paralelismo exige y que están en el código: el `git init` del oráculo
y la lectura de `.gitattributes` se hacen **en serie antes** de abrir el pool (son cachés
perezosas: llenarlas desde dos hilos es una carrera), y el resultado se recoge con
`pool.map`, que preserva el orden de entrada — la matriz no cambia de orden por paralelizarse.

### Censo de la cola: la población se declara antes que el porcentaje

`--prescribir` sobre las **309 ramas** `origin/worker/*` del clon desechable (28-Nov-2026, tronco
`34ee1d2c`, 258 bases distintas, un `diff` por base y por rama — no dos por rama) dio
`AL_DIA` 17 · `REBASAR_LIBRE` 224 · `REBASAR_CON_RIESGO` 68. **Ese 72,5 % era un artefacto
de población, y esta sección lo corrige.** De las 275 refs locales, **213 ya están contenidas
en el tronco** (`git merge-base --is-ancestor`): no tienen commits propios, rebasan limpias
por no tener nada que reaplicar y entraban como `REBASAR_LIBRE`. La población viva es **62**.

| estado (275 refs locales) | v0.6.0 | v0.6.1 |
|---|---|---|
| `SIN_TRABAJO` (ya en el tronco) | — | **213** |
| `AL_DIA` | 7 | 7 |
| `REBASAR_LIBRE` | **215** | **2** |
| `REBASAR_CON_RIESGO` | 53 | 53 |

**Dos poblaciones, no una.** El censo publicado en v0.6.0 enumeró **309** refs en el clon
desechable —34 más de las 275 que el árbol de trabajo tiene cargadas— y dio `AL_DIA` 17 ·
`REBASAR_LIBRE` 224 · `REBASAR_CON_RIESGO` 68. En **ese** marco las contenidas en el tronco son
**218** (`rev-list --count tronco..ref == 0`, medido): v0.6.1 las publica como `SIN_TRABAJO`,
`REBASAR_LIBRE` baja a **6** y quedan **91** vivas. La tabla de arriba es el marco del árbol de
trabajo (275 · 213 · 62) y es la que se rebasó de verdad. Las dos cuentas son correctas y nombran
poblaciones distintas; publicar una sola «la» cifra era el defecto.

**Contra el acto real, con la población declarada** (62 ramas vivas, clon desechable,
`git rebase --rebase-merges` sobre `34ee1d2c8`):

| prescrito | n | rebase limpio | conflicto |
|---|---|---|---|
| `AL_DIA` | 7 | **7** | 0 |
| `REBASAR_LIBRE` | 2 | **2** | 0 |
| `REBASAR_CON_RIESGO` | 53 | 7 | **46** |

**9 de 9 veredictos «sin riesgo» respetados y 0 falsos seguros**; las 46 en conflicto
publicaron **109 rutas, 1 fuera de las clases declaradas** (una `BITACORA/bloque-*.md`
nueva): **0,9 %**. El rezago no es el predictor, y ahora tampoco lo es el tamaño aparente de
la cola.

**El instrumento también tenía su marco.** Sin `--rebase-merges`, 3 ramas `AL_DIA` —con
mergers del tronco dentro de su historia— se leían en conflicto sobre `BITACORA/registro.jsonl`:
el aplanado reaplica commits que el tronco ya tiene. Con el instrumento corregido, 7/7 limpias.
Una rama que ya contiene el tronco no se rebasa: se mide con la pregunta correcta.

**El rezago no es el predictor** —medido sobre la misma cola del 28-Nov-2026—:

| rama | atrás | clases en juego |
|---|---|---|
| `mac/grafo-js-20261029` | **1793** | **2** |
| `voz-rebasada-20261121` | 12 | 1 |
| `cifras-vivas-20261120` | 113 | 5 |
| `voz-terreno-en-el-repo-20261110` | 496 | 2 |

Mil ochocientos commits de rezago con dos clases contra doce commits con una. Cualquier
umbral `τ_lag` que declare «reconstruir el diff neto en vez de rebasar» corta el conjunto
equivocado: **lo que decide es el traslape de clases de rename, no la distancia**.

**La 24/24 de v0.6.0, con su población:** el número se sostiene (24 ramas rebasadas de
verdad, 24 limpias), pero 213 de las 215 «LIBRE» de donde salió ya estaban en el tronco. Lo
que prueba la ley no es esa muestra: es la tabla de 62 ramas vivas de arriba, donde las
`REBASAR_CON_RIESGO` publican sus conflictos dentro de clase con **1 ruta fuera de 109**.

## Lotes: agrupar PRs que conmutan en una sola corrida de CI (`--lotes`)

En un equipo mediano el coste no es el merge: es quemar minutos de CI en serie sobre PRs que
**algebraicamente conmutan**. `--lotes` colorea el grafo de choque y publica las corridas
mínimas sin un solo merge:

```console
$ merge-lattice-governor --base origin/main --lotes --ref rama-a --ref rama-b --ref rama-c
SUJETO · 5 ramas · tronco origin/main (34ee1d2c)
LOTES · 2 corrida(s) de CI · soporte por archivo o prefijo, sin un merge
  pares 10 · seguros 9 (soporte disjunto) · no seguros 1 (comparten archivo o se pelean por un nombre)
  cota inferior del número de lotes: 2 (ramas que tocan un mismo archivo)
  lote 1 (4): rb02, rb04, rb05, rb06
  lote 2 (1): rb07
  la voraz alcanza la cota inferior: el número de lotes es mínimo
```

**El álgebra.** Tras rebasar, dos ramas comparten el tronco como **base común**; un merge a
tres bandas con una sola base no puede chocar entre conjuntos de cambios sobre archivos
disjuntos —donde «disjuntos» incluye que ninguna ruta sea directorio de la otra: `dw` frente
a `dw/inner.txt` no comparten ruta y chocan igual—. Entonces cada clase de color de un grafo
donde la arista es «comparte archivo o prefijo» es un lote que se integra y se prueba entero,
sin conflicto. Coste: **un `diff` por rama**, no `N(N-1)/2` merges.

**La precondición es el error caro, y está declarada en la salida.** La relación es un
enunciado sobre merges **post-rebase**. Medida contra parejas **pre-rebase** —cada rama con
su propia base— publica **40 pares seguros falsos de 105** en la cola del corpus: el choque no
viene del par, viene de que la rama está atrasada y el tronco le tocó el mismo archivo.
Reordenar el plan no lo repara; rebasar sí. Es la tercera aparición de la misma forma —deuda
sin techo, base global frente a `merge-base` por pareja, soporte sin marco—: **una métrica sin
su marco miente en silencio.**

**Medido sobre el marco correcto** (clon desechable, 28-Nov-2026):

| muestra | pares | seguros → limpios | no seguros → conflicto |
|---|---|---|---|
| 15 ramas de la cola, rebasadas | 10 | **9/9** | **1/1** (en el archivo exacto declarado) |
| 24 ramas `REBASAR_LIBRE` de v0.6.0, rebasadas † | 276 | **276/276** | — (ninguna comparte archivo) |

† La muestra de 24 salió de las 215 «LIBRE» de v0.6.0, de las que **213 ya estaban en el
tronco** (§ *la población se declara antes que el porcentaje*): el número se sostiene, la
población no probaba lo que parecía. La fila que prueba la ley es la de 15 ramas.

**Cotas.** `χ(G) ≥ ω(G)`, y `ω(G) ≥ max_archivo |{ramas que lo tocan}|` —toda rama que toca
un archivo es adyacente a todas las demás que lo tocan— es exacta y gratis. La coloración
voraz por grado decreciente da la cota por arriba y **no es mínima**: la coloración exacta es
NP-dura. Cuando ambas coinciden, la salida lo dice (`el número de lotes es mínimo`).

**Límite declarado:** el soporte es por archivo. Dos ramas que tocan el mismo archivo en
líneas distintas pueden mergear limpias y cuentan como `NO SEGURAS`. La relación sirve para
**prometer** lotes, no para descartar pares.

## Límite del driver: se nombra, no se ejecuta

Un `merge=<driver>` en `.gitattributes` corre dentro del merge real, y este instrumento no
lo ejecuta. Por eso el veredicto de esas parejas es **`NO_MEDIDO` con el nombre del driver**,
nunca «limpio»: un driver propio (union, ledger, derivado) puede resolver, abortar o
reescribir, y ejecutarlo desde un instrumento de lectura sería escribir en el sujeto.

## Límite del clon parcial: el predicado exacto lee blobs

`merge-tree --write-tree` **abre los blobs** del sujeto, así que un clon
`--filter=blob:none` (habitual en CI y en asistentes que ahorran disco) falla con
`unable to read blob object <oid>`. Medido el 26-Nov-2026 en `encode/httpx`: el clon
filtrado sale RC 2 nombrando la causa; `git fetch --refetch` repuebla casi todo pero dejó
**un blob pendiente** y volvió a fallar; el clon completo resolvió las 45 parejas
(**42 por teorema, 3 por merge**). El fallo es **ruidoso por diseño** —RC 2 con la causa y
el remedio—, nunca un verde silencioso. La 0.3.1 cambia el mensaje: antes culpaba a la
versión de git.

## Uso

```
merge-lattice-governor --repo . --base origin/main --holgura-inicial X \
                       [--ref REF ...] [--ratio R] [--banda B] \
                       [--max-n 18] [--prioridad RAMA=PESO ...] \
                       [--sin-parejas] [--sin-plan] [--sin-optimizar] \
                       [--prescribir] [--lotes] [--sin-friccion] [--ignorar-driver] \
                       [--jobs N] [--json] [--self-test] [--version]
```

`--holgura-inicial` es **obligatoria**: una solvencia sin punto de partida es una ficción.
Sólo `--sin-plan` la exime, porque un repositorio ajeno no declara esta ley de masa: ahí la
matriz se publica y el plan se declara `NO_MEDIDO` en vez de inventarse con otro techo.

| RC | Significado |
|---|---|
| `0` | el plan integra todas las ramas y ninguna pareja es incompatible |
| `1` | hay una rama que no cabe en ningún orden solvente, una pareja incompatible (conflicto textual, historias ajenas o colisión simbólica), o un duplicado interno en la rama auditada |
| `2` | entrada inválida, o `NO_MEDIDO`: un archivo que no se pudo leer como Python no es un par limpio |

Con `--sin-plan` el conflicto textual es el dato, no la parada: la matriz informa y sale
RC 0. Las otras dos clases **sí paran en ese modo**, y por razones distintas: una
`COLISION_SIMBOLICA_AST` es un hecho sobre el contenido —dos ramas que no pueden convivir—,
y un `NO_MEDIDO` es un archivo que no se pudo leer. `NO_MEDIDO` nunca degrada a 0 en ningún
modo.

Además del plan, imprime un bloque `OPERAR` con las líneas `git merge --no-ff` en el orden
resuelto — el plan no es una opinión, es un guion ejecutable.

Un conflicto textual **no** excluye la rama: se resuelve a mano y sigue. Pero el `git merge`
de ese paso sí se detiene, así que el guion lo dice debajo:

```
  git -C . merge --no-ff origin/pr-401 -m "merge: pr-401"
    ⚠ conflicto textual con pr-402 en tools/panel.py: el merge se detiene, resuelve y commitea
```

Medido el 26-Nov-2026 sobre una cola real de 15 PRs: **74 de 105 parejas** chocan de
verdad, y **61** de ellas en rutas que el merge genérico decide (las otras 13 las decide un
`merge=<driver>` declarado en `.gitattributes` y salen `NO_MEDIDO`). Un plan que imprimiera
`git merge` sin ese aviso fallaría en el primer paso del par, y quien lo corre por primera
vez leería el fallo como que la herramienta no funciona.

| bandera | qué cambia |
|---|---|
| `--sin-optimizar` | corre el merge también cuando el soporte es disjunto: diferencial del teorema, para auditar el atajo |
| `--sin-friccion` | no mide el choque de cada rama con el tronco (una menos por rama atrasada) |
| `--ignorar-driver` | no lee `.gitattributes`: el veredicto es el del merge genérico puro — aproximación declarada, no medida |
| `--jobs N` | hilos de la matriz por parejas (`0` = auto, tope 8; `1` = serie). El orden de la matriz no cambia |

## Ejemplo real

Corrida sobre un tronco de 209 713 líneas de producto. Holgura inicial **−1 020,35**
(deuda heredada, no de esta ventana). Bloque tal como lo imprimió **0.1.1**; 0.1.2 añade la
línea `CRITERIO` y la columna `NO_MEDIDO` a la matriz, sin cambiar ninguna cifra:

```
SUJETO · 4 ramas · tronco origin/main (34ee1d2c)
HOLGURA INICIAL -1020.35 · banda 0.05 · ratio 1.3698

  rama                        base         arnes    vivo     sim    Δholgura
  trinquete-vitrina           34ee1d2c         0    1029       0    +1460.97
  techo-vivo                  34ee1d2c        98       0       0      -98.00
  orden-b3                    34ee1d2c       145       0       0     -145.00
  panel-ratio                 34ee1d2c       151       0       0     -151.00

MATRIZ DE PAREJAS (6 pares)
  CONMUTA_LIMPIO 6 · COLISION_SIMBOLICA_AST 0 · CONFLICTO_TEXTUAL 0 · HISTORIAS_AJENAS 0

PLAN EXACTO · 4/4 integradas
  1. trinquete-vitrina      -1020.35 →      +440.62
  2. techo-vivo              +440.62 →      +342.62
  3. orden-b3                +342.62 →      +197.62
  4. panel-ratio             +197.62 →       +46.62
```

Sin la rama de pago el plan devuelve **0 integradas**: el trinquete no es una rama más, es
la que hace que las otras tres quepan. Y quitar una de las tres de cierre para meter otra
ramas distinta es una decisión aritmética, no de gusto.

## Lo que este instrumento declara y no mide

Un instrumento honesto dice dónde deja de ver.

- **Strictamente `> 0`.** Es **más estricto** que una ley que trunca la deuda a cero y
  cuenta cada toque de piso. Si tu invariante real es «deuda ≤ banda», una rama que aquí
  sale excluida puede ser legal allí: aquí se declara insolvente porque el prefijo queda
  por debajo de cero, y eso es un hecho distinto de una cota de banda.
- **El delta es aditivo y el orden no lo cambia.** Cierto para una ley lineal; falso si
  rebasar una rama cambia su propio diff. El planificador ordena *aterrizajes*, no rebases:
  la atribución al tronco **dice** cuándo el acto es rebasar, pero no rebasa.
- **Conflicto textual medido, sin seguir renombrados a mano.** Se mide con
  `git merge-tree --write-tree` sobre el ODB del sujeto montado por `alternates`, que es el
  merge real incluidos los `merge=<driver>`: los objetos que escribe van a un ODB desechable
  en `tmp`, no al del repositorio auditado. La detección de renombrados es la de `ort` con
  su umbral por defecto, no un `-M` explícito sobre historial completo.
- **Colisión simbólica: Python y métodos de test.** Se detectan `def test_NN…` con ordinal
  y también los `def test_*` sin ordinal (mismo nombre en la misma clase: el segundo pisa al
  primero). El filtro por la base de la pareja evita que un test heredado cuente como
  colisión. Un **duplicado idéntico** —mismo nombre y mismo cuerpo a los dos lados— no es
  colisión: el merge deja el método repetido y las dos copias son la misma función. Se
  publica aparte, en `identicos` por pareja y en el bloque `duplicados`, porque un cero ahí
  significa *mirado y no hay*. No cubre `pytest` parametrizado, `setattr` dinámico ni otros
  lenguajes.
- **El predicado comparaba nombres, y eso no mide pérdida.** Medido el 26-Nov-2026 sobre 15
  PRs reales (105 parejas): 2 parejas marcadas `COLISION_SIMBOLICA_AST` con 75 hallazgos por
  nombre compartido, y los **75 con el cuerpo idéntico** ⇒ 0 tests perdidos. Falsos
  positivos: 75 de 75. Con la huella del cuerpo (`ast.dump` sin números de línea) el número
  real de pérdidas es **0**, y ahora se sabe porque se mide, no porque no se miró.
- **El plan no propone una pareja que choca.** Una colisión simbólica no la arregla el
  orden: si dos ramas declaran el mismo test, sólo una puede aterrizar. El planificador
  recibe el grafo de parejas incompatibles y elige un conjunto independiente, así que la
  excluida **aparece por su nombre** en `excluidas` y el proceso sale con RC 1 (`PARADA`).
  El instrumento no elige por ti cuál de las dos sobrevive: eso es una decisión tuya.
- **Compone parejas y audita una rama sola, pero no las confunde.** Un archivo con dos
  `def test_07_*` en la misma clase es una colisión interna de esa rama: `--sin-plan --ref R`
  la busca contra el merge-base de `R`, con el mismo predicado y el mismo testigo. La unidad
  del *plan* sigue siendo el par; la de la *auditoría* es la rama.
- **Un archivo ilegible no es un archivo sin tests.** `SyntaxError` y `ValueError` (byte
  nulo) se publican como `NO_MEDIDO` con su motivo, y la corrida sale RC 2. Medido el
  25-Nov-2026: dos ramas tocando el mismo archivo, una con un error de sintaxis lejos del
  otro cambio, dan `merge-tree` RC 0 y la matriz decía `CONMUTA_LIMPIO`; el merge real deja
  un archivo que `ast.parse` rechaza. El instrumento no puede ver lo que no puede leer, pero
  sí puede dejar de llamarlo limpio. La matriz sólo lee los archivos que **las dos** ramas
  tocan; el archivo roto de una sola rama lo publica `--sin-plan --ref R`, que audita la rama
  entera contra su base. Los dos modos son complementarios y así se declara.
- **Maximiza el número de ramas integradas por defecto, no la holgura que queda.** Entre un
  plan de 7 ramas que cierra en +125,62 y otro de 6 que cierra en +46,62, elige el de 7. El
  criterio se declara con `--prioridad RAMA=PESO`: con `--ref a --ref b --prioridad a=3
  --prioridad b=0` el mismo motor resuelve el plan estratégico, y el desempate final sigue
  siendo la holgura. Lo que *no* hace es adivinar prioridades: sin `--prioridad`, todas
  pesan 1 y se dice en `CRITERIO`.
- **Exacto hasta `--max-n` (18).** Por encima, el plan pasa a voraz y lo **dice**
  (`exacto: false`): un plan voraz sigue respetando la solvencia de cada prefijo, pero ya
  no garantiza el máximo número de ramas integradas.
- **Mide líneas, no intención.** Un `docstring` que documenta producto sigue siendo arnés
  si vive en `tools/`. La clasificación es por ruta, declarada, no adivinada.

## Salida `--json`

Un solo sobre para los cuatro modos (plan, matriz sola, rama sola, lotes). El consumidor no
necesita saber en cuál está para leerlo:

| Clave | Tipo | Nota |
|---|---|---|
| `schema` | `"merge-lattice-governor/1"` | forma del sobre, no del contenido |
| `criterio` | string | qué se maximizó; sin `--prioridad` se dice que todas pesan 1 |
| `holgura_inicial` | número o `null` | `null` = `NO_MEDIDO`, nunca `0` |
| `ramas[]` | objetos | `arnes`/`vivo`/`sim`/`delta_holgura` valen `null` sin masa; `friccion_con_tronco` es `[]` (medido y limpio) o `null` (no medido, con `--sin-friccion`) |
| `parejas[]` | objetos | `clase` + testigos (`simbolica`, `textual`, `identicos`) + `driver` (rutas con `merge=`), `decision` (`TEOREMA`/`MEDIDO`), `atribucion` (`TRONCO`/`PAR`/`null`), `prefijo[]` (pares `directorio · ruta` que impidieron el atajo por choque archivo/directorio, vacío en el caso normal) e `idempotentes[]` (rutas comunes con la misma firma `(modo, blob)`: rutas que no hacen falta mergear); `ilegibles[]` son motivos completos |
| `decisiones` | objeto | `{TEOREMA, MEDIDO}`: cuántos pares se decidieron sin mergear (soporte disjunto o firma idéntica) |
| `atribucion` | objeto | `{TRONCO, PAR}`: de los pares en conflicto, cuántos se explican por el tronco (reparación: rebasar) |
| `marco` | string | sólo en `--lotes`: la precondición post-rebase que la relación segura exige, publicada con el número |
| `lotes[]` | listas de refs | sólo en `--lotes`: cada lista es una corrida de CI sin choque posible |
| `soportes` | objeto | sólo en `--lotes`: `ref → archivos` del delta, `[]` es medida |
| `cota_inferior` | entero | sólo en `--lotes`: `ω(G) ≥ max_archivo |{ramas}|`, exacta y gratis |
| `minimo_probado` | booleano | sólo en `--lotes`: `true` = la voraz alcanzó la cota, el número de lotes es mínimo |
| `prescripcion` | lista u `null` | el acto por rama `{ref, atras, estado, clases_comunes[], riesgos[], merges}`; en `REBASAR_CON_MERGE_INTERNO` las clases comunes son `[]` y `riesgos` publica lo que la rama toca, porque no hay prueba que dar; `null` = no pedido con `--prescribir`, `[]` no ocurre (siempre hay al menos una rama) |
| `duplicados` | objeto | `duplicados_identicos` (pares de `def`) y `parejas_con_duplicados_identicos` (pares de ramas): dos unidades, dos claves |
| `idempotentes` | objeto | `rutas_idempotentes` (rutas) y `parejas_idempotentes` (pares de ramas): dos unidades, dos claves |
| `ilegibles` | lista de rutas | agregado por ruta; `[]` es medida, no ausencia |
| `resumen` | objeto o `null` | `null` en rama sola: 0 pares no es un resumen |
| `sola` | objeto o `null` | sólo en `--sin-plan --ref R` |
| `plan` | objeto o `null` | `null` cuando no hay holgura que decidir; `plan.textual_en_plan[]` lista `{rama, posicion, con, rutas}` de los pasos que se detienen |

Las claves están siempre: una clave que aparece condicionalmente convierte «no hay» en «no
sé» — medido el 25-Nov-2026 con un consumidor propio que se rompía en `datos["ilegibles"]`
justo cuando no había nada ilegible. En modo rama sola (`--sin-plan --ref R`) `decisiones` y
`atribucion` viajan como objeto vacío: no hay pares que contar, y un cero ahí se leería como
una matriz medida.

## GitHub Actions

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor@v0.9.0
- run: merge-lattice-governor --base origin/main --holgura-inicial 0
         --ref origin/pr-401 --ref origin/pr-402 --ref origin/pr-403
```

(El wheel viaja como artefacto del release mientras no haya PyPI: se instala por URL, y
`pip install merge-lattice-governor` todavía no resuelve.)

## Medido sobre una cola real: 15 PRs, 105 parejas

Antes de tocar un repositorio ajeno, la cola de 15 PRs abiertos de un tronco propio, todas
las parejas (`15·14/2 = 105`), base = `git merge-base` de cada pareja. Cifras de la 0.3.0
(tronco `34ee1d2c`), predicado exacto y driver declarado:

| clase | parejas |
|---|---|
| `CONMUTA_LIMPIO` | 26 |
| `CONFLICTO_TEXTUAL` | 61 |
| `NO_MEDIDO` (ruta con `merge=<driver>` que tocan los dos lados) | 18 |
| `COLISION_SIMBOLICA_AST` | 0 (75 duplicados idénticos, ver abajo) |
| `HISTORIAS_AJENAS` | 0 |

Desglose que la tabla de arriba esconde y que el instrumento publica en `--json`:
`DECISIÓN` **TEOREMA 25 · MEDIDO 80**; `ATRIBUCIÓN` **TRONCO 57 · PAR 4**; 27 parejas tocan
alguna ruta con driver (13 sólo driver, 9 mixtas, 5 sin conflicto genérico).

Tres hechos que sólo aparecen al medir la cola entera y que cambian la conclusión:

1. **Ningún orden de merge era solvente al empezar.** Con holgura inicial −22, el plan
   integraba 0/15. Con una sola rama de pago por delante (+440,62) el mismo motor integra
   7/15 y cada prefijo sigue siendo positivo hasta +125,62. El cuello de botella no era
   encontrar trozos pequeños: era restaurar la cubeta.
2. **74 de los 105 pares chocan de verdad, y 57 de ellos se explican por el tronco.** La 0.2.x
   publicaba 61 porque 13 conflictos ocurrían en rutas gobernadas por `merge=platino-derivado`,
   que no dejan marcas. La cifra vieja no era un error de conteo: era un predicado mirando
   donde el driver no escribe.
3. **Las «2 colisiones simbólicas» no eran colisiones.** 75 parejas de `def` con el mismo
   nombre y 75 cuerpos idénticos: 0 tests perdidos. La cifra publicada el 25-Nov era un
   falso positivo del predicado, y este README lo dice en lugar de borrarla.

## Medido sobre repositorios ajenos

La matriz no se validó sólo con ramas propias. Dos repositorios públicos, diez PRs
abiertos cada uno, todas las parejas (`N·(N−1)/2 = 45` por repo), base **el merge-base de
cada pareja** —verificado igual a `git merge-base A B` en los 90 pares—:

| repositorio | tronco | refs | pares | con archivo común | limpio | textual | simbólico | `NO_MEDIDO` |
|---|---|---|---|---|---|---|---|---|
| `psf/requests` | `origin/main` `3c7baaa0` | 10 | 45 | 44 | 41 | 4 | 0 | 0 |
| `encode/httpx` | `master` `7cff5f79` | 10 | 45 | 25 | 45 | 0 | 0 | 0 |

Los 4 conflictos textuales son todos contra el mismo PR y el mismo archivo
(`src/requests/models.py`): un solo PR mal ubicado ya bloquea cuatro aterrizajes.

Cuánto decide el teorema depende de lo frescas que estén las ramas, y eso se mide: en
`requests` el teorema resuelve **1 de 45** parejas y el merge **44** (10/10 ramas atrasadas);
en `httpx`, **42 y 3** (2/10 atrasadas). La atribución de `requests` deja los 4 conflictos
enteros en el tronco (**`TRONCO 4 · PAR 0`**), que es exactamente lo que predice la sección
siguiente. Medido el 26-Nov-2026 con la 0.3.0.

La columna que importa para el predicado simbólico es la de **oportunidades**: parejas donde
los dos lados añaden algún `def test…` en la misma `(archivo, clase)` —el único escenario
donde puede haber shadowing—. Son **6/45** en `requests` y **3/45** en `httpx`; en las 9 se
examinaron los símbolos y **0 chocaron** (0 ordinales compartidos, 0 nombres compartidos).
Eso no es un defecto del predicado: es que ahí no había nada que encontrar, y por eso el
marcador dice «examinado y limpio» en vez de «no mirado». Los testigos de fuego real están
donde sí los hubo: 20 coincidencias ingenuas → **1** colisión intra-clase en un corpus
propio, y 3 → 1 por pareja.

Métodos de test nuevos en el periodo: 14 en 6/10 ramas (`requests`) y 54 en 6/10 (`httpx`).

```bash
git clone https://github.com/psf/requests && cd requests
git fetch origin 'refs/pull/*/head:refs/heads/pr-*'
merge-lattice-governor --base origin/main --sin-plan --json \
    --ref pr-7184 --ref pr-7194 --ref pr-7201 --ref pr-7213 --ref pr-7217 \
    --ref pr-7388 --ref pr-7415 --ref pr-7471 --ref pr-7513 --ref pr-7520
```

Nada de esto escribe en el repositorio auditado: `merge-tree --write-tree` escribe sus
objetos en un ODB desechable en `tmp` que ve el ODB del sujeto por `alternates`, así que ni
el ODB ni el índice del sujeto se tocan. Requiere git ≥ 2.38 (probado con 2.39.5); el
predicado exacto necesita `merge-tree --write-tree`, que es de 2.38 en adelante.

## Réplica: otra muestra, mismo veredicto

Elegir la muestra y publicar el resultado deja abierta la objeción de sesgo de selección.
Segunda pasada con un muestreo distinto —los diez PRs abiertos que tocaban `.py` en el momento
de medir—, mismos troncos, todas las parejas:

| repositorio | pares | limpio | textual | simbólico | discrepancias vs `git merge-tree` |
|---|---|---|---|---|---|
| `psf/requests` | 45 | 38 | 7 | 0 | **0/45** |
| `encode/httpx` | 45 | 45 | 0 | 0 | **0/45** |

El eje simbólico se recalculó por fuera del motor, sobre los símbolos que cada rama **añade**
(no los que hereda: `PreparedRequest.__init__` existe en las dos ramas porque existe en el
tronco, y no es una colisión): 0 choques, 0 discrepancias. Con eso el eje textual y el
simbólico tienen auditoría independiente sobre 90 parejas ajenas; el eje simbólico **no tuvo
ocasión de disparar** en ellas, y su testigo de fuego sigue siendo el corpus propio (20 → 1).

### Un conflicto de pareja puede tener al tronco por contraparte

Los 7 conflictos de `requests` tienen todos el mismo lado: `pr-7388`. No es una rama fresca:
su base está **57 commits atrás** (104 en `pr-7194`; **10/10** ramas de `requests` van
atrasadas, frente a **2/10** de `httpx`, con 4). Al fusionar `pr-7520` × `pr-7388` el
merge-base de la pareja es el tronco viejo, así que el lado de `pr-7520` arrastra los cambios
que el **tronco** hizo en `src/requests/models.py` desde entonces. El conflicto es real, pero
su contraparte no es el otro PR: es el tronco.

Medido, no inferido: `git rebase main` sobre `pr-7388` en un worktree desechable conflictúa en
**el mismo archivo**. Consecuencia operativa: **reordenar el plan no repara ese conflicto**
—todo orden pone a `pr-7388` junto al tronco— y el acto de reparación es uno solo: rebasar la
rama atrasada, no reasignar vértices.

Corolario que corrige el criterio ingenuo: «soporte textual disjunto ⇒ conmuta» es **falso**.
En esta muestra, 4 de las 7 parejas conflictivas tienen soporte disjunto *medido contra el
tronco* (`pr-7520` toca `utils.py`, `pr-7388` toca `models.py`) y aun así chocan. El soporte
de una rama no es propiedad de la rama: es propiedad del marco en que se mide, y el único
marco que decide es el merge-base de la pareja. Por eso la columna «con archivo común» de la
tabla anterior se calcula contra la base de cada pareja y no contra el tronco: contra el
tronco habría escondido exactamente estas cuatro.

```bash
# Muestra de la réplica: los diez PRs abiertos que tocaban .py, base = merge-base de la pareja
merge-lattice-governor --base main --sin-plan --json \
    --ref pr-7194 --ref pr-7213 --ref pr-7388 --ref pr-7413 --ref pr-7415 \
    --ref pr-7446 --ref pr-7471 --ref pr-7506 --ref pr-7513 --ref pr-7520
```

## La muestra sembrada (28-Nov-2026): la anterior no era la que decía

La corrida del 27-Nov publicó 2 340 parejas de tres colas ajenas (`tiangolo/typer`,
`encode/httpx`, `psf/black`) declarando sus cifras **cota superior por edad**, porque creía
haber tomado las 40 PRs abiertas más antiguas. No lo eran: era la **primera página** de
`gh pr list --limit 40`, ordenada por actividad, que en `typer` deja fuera las 6 PRs abiertas
de número más bajo. La corrección vive en
[`evidencia/2026-11-27/`](evidencia/2026-11-27/README.md), en la cabecera.

Se rehizo con procedencia reproducible: población completa (`gh pr list --limit 1000` → **46 ·
104 · 74** abiertas) y **muestra aleatoria uniforme** `--muestra 40 --semilla 20261128` sobre
la población ordenada numéricamente, con los 40 números elegidos publicados. 780 parejas por
sujeto, base = merge-base de la pareja:

| cola | `k = 1` (una ruta común) | `k ≥ 2` | salto |
|---|---|---|---|
| `tiangolo/typer` | 0,2934 [0,2460·0,3457] | 0,5353 [0,4822·0,5876] | **+24,2** |
| `encode/httpx` | 0,2905 [0,2368·0,3507] | 0,8235 [0,7654·0,8697] | **+53,0** |
| `psf/black` | 0,0748 [0,0465·0,1180] | 0,7636 [0,7243·0,7989] | **+68,9** |

Lo que sobrevive: la **dirección** en 3/3 colas y el salto ≥ +15 puntos en 3/3, predichos a
las 08:24 CST antes de medir. Lo que se **refuta**: la cota no era cota — la muestra uniforme
rompe *más* que la página de actividad (`httpx` 0,7817 → 0,8235; `black` 0,7126 → 0,7636), y
las magnitudes salieron por encima de las predichas en los tres sujetos. `k = 0` sigue en
**0 roturas sobre 529 parejas** (`black`: de `n = 3` a `n = 71`), pero ese cero es el atajo
por soporte disjunto, no un hallazgo.

Recibos, muestra elegida y agregación sin `git`:
[`evidencia/2026-11-28/`](evidencia/2026-11-28/README.md).

## Conformidad medida

El predicado de colisión de este paquete se mide contra
[`composicion-core`](https://github.com/alexisromtz-lab/composicion-core), que publica el
corpus de conformidad como datos y puntúa a cada herramienta contra él:

```bash
composicion-core --sonda governor --ruta .
```

Marcador del 26-Nov-2026, corpus de 14 casos y cuatro canales: **11 rojo · 9 aviso · 9
no_medido · 9 identico · 0 discrepancias · 1 no comparable**. `composicion-core` no es una dependencia —estos paquetes siguen sin
dependencias de terceros— sino un juez externo: si los dos divergen, el que se equivoca se
ve.

El único caso no comparable es `aviso-global`: este paquete **no tiene canal de avisos**, así
que el juez no puede puntuar un aviso donde no hay dónde emitirlo. Es una frontera de
contrato declarada, no una discrepancia escondida; los otros tres huecos (rama sola,
`NO_MEDIDO`, duplicado interno) se cerraron en 0.1.2 y el juez los puntúa.

La **arquitectura del propio paquete** la certifica su herramienta hermana en CI, en un job
aparte para que un escáner caído no se confunda con un test rojo:

```yaml
- run: uvx --from platino-scan==1.5.3 platino-scan .
```

Medido el 28-Nov-2026 sobre `main`: `ARQUITECTURA SANA`, RC 0 — 18 archivos de producto, 9 de
pruebas, dos puertas declaradas por encima del umbral.

## La nota técnica — la ley, medida y con DOI

La ley de este paquete (clases de rename ⇒ cota de conflictos de rebase) está publicada como
nota técnica en inglés, con las dos poblaciones del censo declaradas, el instrumento
(`git rebase --rebase-merges`) que sin el flag fabricaba conflictos, y la ley del diff neto
contra el replay que acota lo que la cota no puede ver:

**[Algebraic Merge Queues: bounding Git rebase conflicts without reading blobs](docs/nota-tecnica-en.md)**
· DOI de todas las versiones [`10.5281/zenodo.24548463`](https://doi.org/10.5281/zenodo.24548463)
(estable entre depósitos)
· DOI de esta versión, `1.3` [`10.5281/zenodo.24571247`](https://doi.org/10.5281/zenodo.24571247)
· `1.2` [`10.5281/zenodo.24570948`](https://doi.org/10.5281/zenodo.24570948)
· `1.1` [`10.5281/zenodo.24564357`](https://doi.org/10.5281/zenodo.24564357)
· `1.0` [`10.5281/zenodo.24548464`](https://doi.org/10.5281/zenodo.24548464)
· CC-BY-4.0, depositada con la evidencia en JSON que cita.

## Licencia

MIT. Ver [LICENSE](LICENSE).

## La familia

Tres paquetes con cero dependencias, probados en 3.11, 3.12 y 3.13:

| paquete | qué contesta |
|---|---|
| [composicion-core](https://github.com/alexisromtz-lab/composicion-core) | ¿dos ramas declaran el mismo test? predicado + corpus + juez de paridad |
| [py-test-shadow-guard](https://github.com/alexisromtz-lab/py-test-shadow-guard) | el test que el merge borra en silencio, en tu CI |
| [merge-lattice-governor](https://github.com/alexisromtz-lab/merge-lattice-governor) | en qué orden aterrizar N ramas sin romper el trinquete |
