# Evidencia de la ley, 26-Nov-2026 — tres sujetos y la corrección 6.1

Este directorio existe para que **§6 y §6.1 de [`docs/nota-tecnica-en.md`](../../docs/nota-tecnica-en.md)
se puedan recalcular sin descargar el ZIP de Zenodo**. Los tres sujetos son repositorios
públicos y lo que se guarda son rutas, no contenido.

## Población medida

Ramas **con trabajo propio** (≥1 commit fuera del `merge-base` con su tronco). Las ramas ya
integradas no cuentan: no piden acto. Cifras leídas de los tres TSV de este directorio.

| sujeto | ramas con trabajo | con conflicto | rutas en conflicto | cubiertas a nivel ruta |
|---|---|---|---|---|
| `primer` | 56 | 33 | 65 | 65 |
| `psf/requests` | 40 | 8 | 11 | 10 (la 11.ª, por clase de renombrado) |
| `platino-labs` | 114 | 91 | 159 | 158 |
| **total** | **210** | **132** | **235** | **233** |

La única ruta que **ninguna** clase junta, en `platino-labs`:
`BITACORA/bloque-446-la-cascada-del-pin-cierra-en-un-acto.md` — un add/add entre dos bloques de
bitácora con nombres distintos, sin renombrado que los relacione.

## La corrección: `REBASAR_LIBRE` pide historia lineal

Pre-guardia, la cota estrecha declaraba libres **23** ramas en los tres sujetos. Medidas contra
el rebase real ([`libre.tsv`](libre.tsv)):

| régimen | n | con conflicto |
|---|---|---|
| `rev-list --merges --count base..ref == 0` | 22 | **0** |
| con un merge dentro | 1 | **1** |

El caso: `psf/requests` **`pr/7065`**, merge `fe0853c6` (*Merge branch 'main' into edit-14*). Su
segundo padre **es** el `merge-base`, y `git merge-tree` **de sus propios padres** choca en los
mismos tres archivos en que para el rebase (`src/requests/adapters.py`,
`src/requests/models.py`, `tests/test_adapters.py`). Es un merge *malvado*: la resolución vive
sólo en el árbol del merge y el replay no la reproduce — un merge no se re-aplica, se re-ejecuta.

Por eso `v0.8.0` añade `REBASAR_CON_MERGE_INTERNO`; en `libre.tsv` la última columna publica el
veredicto de esta versión sobre las mismas 23 ramas: **22 `REBASAR_LIBRE` · 1 `REBASAR_CON_MERGE_INTERNO`**.

## Cómo se recalcula

```bash
PY=python3                                        # 3.11+ (el paquete usa `X | None`)

$PY census_con_merges.py REPO TRONCO [REF...]     # censo + merges internos → JSON
$PY cobertura.py         REPO TRONCO REF...       # rebase real → TSV de cobertura
$PY ley_s6_multisujeto.py REPO TRONCO [REF...]    # cota estrecha vs ancha vs replay → JSON
$PY ley_merge_interno.py REPO TRONCO COB.tsv      # separación lineal / merge interno
$PY cruce.py SUJETO REPO CENSO.json COB.tsv       # veredicto × acto, por régimen de atraso
```

Sin `REF...` los scripts usan `refs/remotes/origin/*` del clon. `cobertura.py` **rebasa de
verdad**, en clon desechable y con `rerere.enabled=false`: es la única pieza que escribe, y sólo
en el clon.

| archivo | qué guarda |
|---|---|
| `cob_primer.tsv` · `cob_req.tsv` · `cob_labs.tsv` | una fila por rama: atrás · cota estrecha · cota ancha · paro · rutas en conflicto · cubiertas · solo-ancha · no cubiertas |
| `libre.tsv` | las 23 ramas que la cota declaró libres: merges · paro · conflictos · estado en v0.8.0 |
| `req_prs.tsv` | mapa `pr/…` ↔ número de PR en `psf/requests` |
| `*.py` | censo, cobertura, ley y cruce; releen los TSV sin red |

## Protocolo declarado

La cobertura de estos TSV usa el **primer paro** del rebase. La cifra de §6 (22 ramas · 67 rutas)
usó **replay completo con resolución**: no son comparables, y la corrección de 6.1 se apoya sólo
en el primer paro.
