# merge-lattice-governor

**El orden en que aterrizas tus ramas decide si el trinquete aguanta.** Este CLI mide las
masas de cada rama, comprueba qué parejas conmutan de verdad (texto **y** símbolos), y
resuelve por programación dinámica la secuencia exacta en la que **cada prefijo** sigue
siendo solvente.

Sin dependencias. Python ≥ 3.11. Cero escrituras en el repositorio que audita.

```console
$ uvx merge-lattice-governor --base origin/main --holgura-inicial -1020.35 \
    --ref rama-pago --ref pr-402 --ref pr-401 --ref pr-403
```

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
                       [--max-n 18] [--sin-parejas] [--json] [--self-test] [--version]
```

`--holgura-inicial` es **obligatoria**: una solvencia sin punto de partida es una ficción.

| RC | Significado |
|---|---|
| `0` | el plan integra todas las ramas y ninguna pareja es incompatible |
| `1` | hay una rama que no cabe en ningún orden solvente, o una pareja con conflicto textual o colisión simbólica |
| `2` | entrada inválida: referencia ilegible, repo ausente, falta `--ref` o `--holgura-inicial` |

Además del plan, imprime un bloque `OPERAR` con las líneas `git merge --no-ff` en el orden
resuelto — el plan no es una opinión, es un guion ejecutable.

## Ejemplo real

Corrida sobre un tronco de 209 713 líneas de producto. Holgura inicial **−1 020,35**
(deuda heredada, no de esta ventana):

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
- **Compone parejas, no audita una rama sola.** Un archivo con dos `def test_07_*` en la
  misma clase es una colisión interna de esa rama y este paquete no la busca: su unidad es
  el par. Para eso está `py-test-shadow-guard`.
- **Exacto hasta `--max-n` (18).** Por encima, el plan pasa a voraz y lo **dice**
  (`exacto: false`): un plan voraz sigue respetando la solvencia de cada prefijo, pero ya
  no garantiza el máximo número de ramas integradas.
- **Mide líneas, no intención.** Un `docstring` que documenta producto sigue siendo arnés
  si vive en `tools/`. La clasificación es por ruta, declarada, no adivinada.

## GitHub Actions

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: pip install merge-lattice-governor
- run: merge-lattice-governor --base origin/main --holgura-inicial 0
         --ref origin/pr-401 --ref origin/pr-402 --ref origin/pr-403
```

## Conformidad medida

El predicado de colisión de este paquete se mide contra
[`composicion-core`](https://github.com/alexisromtz-lab/composicion-core), que publica el
corpus de conformidad como datos y puntúa a cada herramienta contra él:

```bash
composicion-core --sonda governor --ruta .
```

Marcador del 26-Nov-2026: **8 rojo · 8 aviso · 6 no_medido · 0 discrepancias · 4 no comparables**. `composicion-core` no es una dependencia
—estos paquetes siguen sin dependencias para poder correr con `uvx`— sino un juez
externo: si los dos divergen, el que se equivoca se ve.

## Licencia

MIT. Ver [LICENSE](LICENSE).
