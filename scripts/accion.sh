#!/usr/bin/env bash
# Cuerpo de la acción compuesta: arma el argv desde las entradas y devuelve el RC del
# gobernador sin traducirlo. Un RC traducido aquí sería un segundo contrato que puede
# divergir del primero; el que manda es el del CLI.
#
# Corrible fuera de CI con las mismas variables que declara action.yml:
#   INPUT_BASE=origin/main INPUT_HOLGURA=46.62 INPUT_REFS="origin/pr-1 origin/pr-2" \
#   GITHUB_WORKSPACE=$PWD scripts/accion.sh
set -uo pipefail

repo="${INPUT_REPO:-${GITHUB_WORKSPACE:-$PWD}}"
base="${INPUT_BASE:-origin/main}"
holgura="${INPUT_HOLGURA:-}"
refs="${INPUT_REFS:-}"
extra="${INPUT_ARGUMENTOS:-}"
salida="${INPUT_SALIDA_JSON:-}"

if [ -z "$holgura" ]; then
  echo "merge-lattice-governor: falta el input holgura-inicial" >&2
  echo "una solvencia sin punto de partida es una ficción: el plan se declara NO_MEDIDO" >&2
  exit 2
fi
if [ -z "$refs" ]; then
  echo "merge-lattice-governor: falta el input refs (separadas por espacio o coma)" >&2
  exit 2
fi

argv=(--repo "$repo" --base "$base" --holgura-inicial "$holgura")
for ref in ${refs//,/ }; do
  argv+=(--ref "$ref")
done
if [ -n "${INPUT_RATIO:-}" ]; then argv+=(--ratio "$INPUT_RATIO"); fi
if [ -n "${INPUT_BANDA:-}" ]; then argv+=(--banda "$INPUT_BANDA"); fi
# shellcheck disable=SC2206  # el operador declara argumentos sueltos a propósito
if [ -n "$extra" ]; then argv+=($extra); fi

if [ -n "$salida" ]; then
  mkdir -p "$(dirname "$salida")"
  merge-lattice-governor "${argv[@]}" --json > "$salida"
  rc=$?
  echo "merge-lattice-governor: JSON en $salida · RC $rc" >&2
  exit $rc
fi

merge-lattice-governor "${argv[@]}"
exit $?
