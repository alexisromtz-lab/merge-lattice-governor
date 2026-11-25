# merge-lattice-governor

**El orden en que aterrizas tus ramas decide si el trinquete aguanta.** Este CLI mide las
masas de cada rama, comprueba qué parejas conmutan de verdad (texto **y** símbolos), y
resuelve por programación dinámica la secuencia exacta en la que **cada prefijo** sigue
siendo solvente.

Sin dependencias. Python ≥ 3.11. Cero escrituras en el repositorio que audita.

```console
$ pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor.git
$ merge-lattice-governor --base origin/main --holgura-inicial -1020.35 \
    --ref rama-pago --ref pr-402 --ref pr-401 --ref pr-403
```

Sin PyPI todavía: se instala desde el repositorio, no por nombre corto —`uvx
merge-lattice-governor` no resuelve mientras no haya wheel publicado—.
---

## El problema

Con 8–30 PRs abiertos, un merge queue ordena por llegada. Nadie te dice que la rama que
llegó tercera consume el presupuesto que la séptima necesitaba para no romper el trinquete,
ni que dos ramas que Git fusiona «limpias» declaran el mismo `test_35` en la misma clase y
Python resuelve el empate **borrando un test en silencio**.

Tres puntos ciegos, los tres medidos:

| Punto ciego | Qué se pierde | Cómo lo mide esta herramienta |
|---|---|---|
| El orden no se mira | un prefijo insolvente aunque el final sea verde | DP exacto sobre subconjuntos: `factible[S]` sólo si **algún** orden de `S` deja todos sus prefijos `> 0` |
| La base es global | conflictos inventados al comparar N ramas de un mismo tronco | `git merge-base` **por pareja** para conflicto y **por rama** para masa |
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

## Uso

```
merge-lattice-governor --repo . --base origin/main --holgura-inicial X \
                       [--ref REF ...] [--ratio R] [--banda B] \
                       [--max-n 18] [--prioridad RAMA=PESO ...] \
                       [--sin-parejas] [--sin-plan] [--json] [--self-test] [--version]
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
RC 0. `NO_MEDIDO` nunca degrada a 0 en ningún modo.

Además del plan, imprime un bloque `OPERAR` con las líneas `git merge --no-ff` en el orden
resuelto — el plan no es una opinión, es un guion ejecutable.

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
  rebasar una rama cambia su propio diff. El planificador ordena *aterrizajes*, no rebases.
- **Conflicto textual sin detección de renombrados.** Se mide con `git merge-tree` en su
  forma de tres argumentos, que no escribe objetos en el ODB: el discriminante son las
  marcas `<<<<<<< .our`, porque `changed in both` aparece también en los merges limpios
  (verificado: `merge-tree` devuelve **RC 0 siempre**).
- **Colisión simbólica: Python y métodos de test.** Se detectan `def test_NN…` con ordinal
  y también los `def test_*` sin ordinal (mismo nombre en la misma clase: el segundo pisa al
  primero). El filtro por la base de la pareja evita que un test heredado cuente como
  colisión. No cubre `pytest` parametrizado, `setattr` dinámico ni otros lenguajes.
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

Un solo sobre para los tres modos (plan, matriz sola, rama sola). El consumidor no
necesita saber en cuál está para leerlo:

| Clave | Tipo | Nota |
|---|---|---|
| `schema` | `"merge-lattice-governor/1"` | forma del sobre, no del contenido |
| `criterio` | string | qué se maximizó; sin `--prioridad` se dice que todas pesan 1 |
| `holgura_inicial` | número o `null` | `null` = `NO_MEDIDO`, nunca `0` |
| `ramas[]` | objetos | `arnes`/`vivo`/`sim`/`delta_holgura` valen `null` sin masa |
| `parejas[]` | objetos | `clase` + testigos; `ilegibles[]` son motivos completos |
| `ilegibles` | lista de rutas | agregado por ruta; `[]` es medida, no ausencia |
| `resumen` | objeto o `null` | `null` en rama sola: 0 pares no es un resumen |
| `sola` | objeto o `null` | sólo en `--sin-plan --ref R` |
| `plan` | objeto o `null` | `null` cuando no hay holgura que decidir |

Las claves están siempre: una clave que aparece condicionalmente convierte «no hay» en «no
sé» — medido el 25-Nov-2026 con un consumidor propio que se rompía en `datos["ilegibles"]`
justo cuando no había nada ilegible.

## GitHub Actions

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor.git
- run: merge-lattice-governor --base origin/main --holgura-inicial 0
         --ref origin/pr-401 --ref origin/pr-402 --ref origin/pr-403
```

(Sin wheel publicado, la instalación es por URL de repositorio; `pip install
merge-lattice-governor` no resuelve todavía.)

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
git clone --filter=blob:none https://github.com/psf/requests && cd requests
git fetch origin 'refs/pull/*/head:refs/heads/pr-*'
merge-lattice-governor --base origin/main --sin-plan --json \
    --ref pr-7184 --ref pr-7194 --ref pr-7201 --ref pr-7213 --ref pr-7217 \
    --ref pr-7388 --ref pr-7415 --ref pr-7471 --ref pr-7513 --ref pr-7520
```

Nada de esto escribe en el repositorio auditado: `merge-tree` en su forma de tres argumentos
no toca el ODB ni el índice. Requiere git ≥ 2.38 (probado con 2.39.5).

## Conformidad medida

El predicado de colisión de este paquete se mide contra
[`composicion-core`](https://github.com/alexisromtz-lab/composicion-core), que publica el
corpus de conformidad como datos y puntúa a cada herramienta contra él:

```bash
composicion-core --sonda governor --ruta .
```

Marcador del 25-Nov-2026: **9 rojo · 9 aviso · 9 no_medido · 0 discrepancias · 1 no
comparable**. `composicion-core` no es una dependencia —estos paquetes siguen sin
dependencias de terceros— sino un juez externo: si los dos divergen, el que se equivoca se
ve.

El único caso no comparable es `aviso-global`: este paquete **no tiene canal de avisos**, así
que el juez no puede puntuar un aviso donde no hay dónde emitirlo. Es una frontera de
contrato declarada, no una discrepancia escondida; los otros tres huecos (rama sola,
`NO_MEDIDO`, duplicado interno) se cerraron en 0.1.2 y el juez los puntúa.

## Licencia

MIT. Ver [LICENSE](LICENSE).
