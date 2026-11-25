# merge-lattice-governor

[![ci](https://github.com/alexisromtz-lab/merge-lattice-governor/actions/workflows/ci.yml/badge.svg)](https://github.com/alexisromtz-lab/merge-lattice-governor/actions/workflows/ci.yml) ![python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue) ![deps](https://img.shields.io/badge/dependencies-0-brightgreen) ![license](https://img.shields.io/badge/license-MIT-blue)

**El orden en que aterrizas tus ramas decide si el trinquete aguanta.** Este CLI mide las
masas de cada rama, comprueba qué parejas conmutan de verdad (texto **y** símbolos), y
resuelve por programación dinámica la secuencia exacta en la que **cada prefijo** sigue
siendo solvente.

Sin dependencias. Python ≥ 3.11. Cero escrituras en el repositorio que audita. La suite
tampoco arrastra ninguna: `python -m unittest discover -s tests -t .` corre en un intérprete
pelado —108 pruebas, medido en un Python 3.12 sin PyYAML—.

```console
$ pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor@v0.4.1
$ merge-lattice-governor --base origin/main --holgura-inicial -1020.35 \
    --ref rama-pago --ref pr-402 --ref pr-401 --ref pr-403
```

Sin PyPI todavía: se instala desde el repositorio, no por nombre corto —`uvx
merge-lattice-governor` no resuelve mientras no haya wheel publicado—.

### Como hook de `pre-commit`

```yaml
repos:
  - repo: https://github.com/alexisromtz-lab/merge-lattice-governor
    rev: v0.4.1
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
      - uses: alexisromtz-lab/merge-lattice-governor@v0.4.1
        with:
          holgura-inicial: "46.62"          # obligatoria: la ley de masa es tuya
          refs: "origin/pr-402 origin/pr-401 origin/pr-403"
          salida-json: artefactos/plan.json
```

El **RC del gobernador es el RC del paso**: un plan insolvente tumba el check en vez de
publicarse como verde. Entradas: `holgura-inicial` · `refs` · `base` (por defecto
`origin/main`) · `repo` (vacío = el workspace) · `ratio` · `banda` · `argumentos` ·
`salida-json`. Salida `rc` para consumirla en pasos posteriores.

Se recomienda fijar la etiqueta exacta (`@v0.4.1`). Este repositorio **no** mantiene una
etiqueta móvil `@v0`: una referencia mutable que promete lo que dice una versión fija es la
misma clase de defecto que un plan sin su marco —no se puede citar lo que cambia solo—.

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
                       [--sin-friccion] [--ignorar-driver] \
                       [--json] [--self-test] [--version]
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

Un solo sobre para los tres modos (plan, matriz sola, rama sola). El consumidor no
necesita saber en cuál está para leerlo:

| Clave | Tipo | Nota |
|---|---|---|
| `schema` | `"merge-lattice-governor/1"` | forma del sobre, no del contenido |
| `criterio` | string | qué se maximizó; sin `--prioridad` se dice que todas pesan 1 |
| `holgura_inicial` | número o `null` | `null` = `NO_MEDIDO`, nunca `0` |
| `ramas[]` | objetos | `arnes`/`vivo`/`sim`/`delta_holgura` valen `null` sin masa; `friccion_con_tronco` es `[]` (medido y limpio) o `null` (no medido, con `--sin-friccion`) |
| `parejas[]` | objetos | `clase` + testigos (`simbolica`, `textual`, `identicos`) + `driver` (rutas con `merge=`), `decision` (`TEOREMA`/`MEDIDO`) y `atribucion` (`TRONCO`/`PAR`/`null`); `ilegibles[]` son motivos completos |
| `decisiones` | objeto | `{TEOREMA, MEDIDO}`: cuántos pares se decidieron por soporte disjunto sin mergear |
| `atribucion` | objeto | `{TRONCO, PAR}`: de los pares en conflicto, cuántos se explican por el tronco (reparación: rebasar) |
| `duplicados` | objeto | `duplicados_identicos` (pares de `def`) y `parejas_con_duplicados_identicos` (pares de ramas): dos unidades, dos claves |
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
- run: pip install git+https://github.com/alexisromtz-lab/merge-lattice-governor@v0.4.1
- run: merge-lattice-governor --base origin/main --holgura-inicial 0
         --ref origin/pr-401 --ref origin/pr-402 --ref origin/pr-403
```

(Sin wheel publicado, la instalación es por URL de repositorio; `pip install
merge-lattice-governor` no resuelve todavía.)

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

## Licencia

MIT. Ver [LICENSE](LICENSE).

## La familia

Tres paquetes con cero dependencias, probados en 3.11, 3.12 y 3.13:

| paquete | qué contesta |
|---|---|
| [composicion-core](https://github.com/alexisromtz-lab/composicion-core) | ¿dos ramas declaran el mismo test? predicado + corpus + juez de paridad |
| [py-test-shadow-guard](https://github.com/alexisromtz-lab/py-test-shadow-guard) | el test que el merge borra en silencio, en tu CI |
| [merge-lattice-governor](https://github.com/alexisromtz-lab/merge-lattice-governor) | en qué orden aterrizar N ramas sin romper el trinquete |
