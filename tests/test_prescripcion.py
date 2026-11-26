"""Ley del acto: la identidad de una ruta no es su nombre.

Medido el 27-Nov-2026 sobre los PRs abiertos más viejos de `psf/requests` (12 ramas):
comparando **nombres** de ruta, 11 de 17 conflictos caían fuera de la predicción, porque
el tronco había renombrado `requests/models.py` → `src/requests/models.py` y la rama tocó
el nombre viejo. Agrupando por clase de rename: 0 de 17 fuera. Corpus del 15 ramas: 0 de
10 fuera.

Estos tests fijan las dos mitades: la clase acierta y el nombre se queda corto.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from merge_lattice_governor import rebase as B  # noqa: E402
from merge_lattice_governor import repo as R  # noqa: E402

CUERPO = "\n".join(f"linea_{i} = {i}" for i in range(40)) + "\n"


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True)
    return out.stdout


class Sujeto(unittest.TestCase):
    """Un tronco que renombra el archivo que una rama atrasada editó."""

    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-rebase-")
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("init", "-q", "-b", "main")
        g("config", "user.email", "sonda@ejemplo")
        g("config", "user.name", "sonda")
        for nombre in ("a.py", "z.py"):
            with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
                f.write(CUERPO)
        g("add", "-A")
        g("commit", "-qm", "base")

        g("checkout", "-q", "-b", "toca-viejo")
        self._escribir("a.py", CUERPO.replace("linea_5 = 5", "linea_5 = 55"))
        g("commit", "-qam", "rama: toca el nombre viejo")

        g("checkout", "-q", "main")
        g("checkout", "-q", "-b", "toca-otro")
        self._escribir("z.py", CUERPO.replace("linea_30 = 30", "linea_30 = 3030"))
        g("commit", "-qam", "rama: toca un archivo que el tronco no toca")

        g("checkout", "-q", "main")
        g("mv", "a.py", "b.py")
        self._escribir("b.py", CUERPO.replace("linea_5 = 5", "linea_5 = 555"))
        g("commit", "-qam", "tronco: renombra y edita")
        g("branch", "ya-fundida", "main~1")

        g("checkout", "-q", "-b", "al-dia")
        self._escribir("z.py", CUERPO.replace("linea_1 = 1", "linea_1 = 101"))
        g("commit", "-qam", "al-dia: trabajo propio sobre el tronco ya presente")

    def tearDown(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _escribir(self, nombre: str, texto: str) -> None:
        with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
            f.write(texto)

    def prescripciones(self) -> dict[str, B.Prescripcion]:
        refs = ["toca-viejo", "toca-otro", "al-dia", "ya-fundida"]
        return {p.ref: p for p in B.prescribir(self.raiz, "main", refs)}


class LaClaseAcierta(Sujeto):
    def test_el_rename_mete_el_nombre_nuevo_en_la_clase(self) -> None:
        p = self.prescripciones()["toca-viejo"]
        self.assertEqual(p.estado, B.REBASAR_CON_RIESGO)
        self.assertIn("b.py", p.clases, "el nombre que verá el operador es el del tronco")
        self.assertIn("a.py", p.clases, "y el que la rama tocó, para poder reconciliarlos")

    def test_el_conflicto_predicho_existe_de_verdad(self) -> None:
        """Sin esto la predicción sería vacua: `b.py` sí choca al fundir el tronco."""
        reales = R.rutas_en_conflicto(self.raiz, "main", "toca-viejo")
        self.assertEqual(reales, ("b.py",))

    def test_sin_clases_comunes_el_rebase_es_libre(self) -> None:
        p = self.prescripciones()["toca-otro"]
        self.assertEqual(p.estado, B.REBASAR_LIBRE)
        self.assertEqual(p.clases, ())
        self.assertEqual(R.rutas_en_conflicto(self.raiz, "main", "toca-otro"), ())

    def test_la_rama_que_ya_tiene_el_tronco_no_pide_acto(self) -> None:
        p = self.prescripciones()["al-dia"]
        self.assertEqual(p.estado, B.AL_DIA)
        self.assertEqual(p.atras, 0)


class LaRamaYaFundidaNoInflaElCenso(Sujeto):
    """213 de las 275 refs del corpus estaban ya en el tronco.

    Sin `SIN_TRABAJO` entraban como `REBASAR_LIBRE` —rebase limpio por no tener nada que
    reaplicar— y publicaban «72,5 % de la cola pide rebase probado» sobre una población
    que en su mayoría no tenía commits propios. El estado nombra lo que la rama es.
    """

    def test_la_rama_contenida_se_nombra_y_no_se_cuenta_libre(self) -> None:
        p = self.prescripciones()["ya-fundida"]
        self.assertEqual(p.estado, B.SIN_TRABAJO)
        self.assertEqual(p.atras, 1, "el tronco le lleva un commit, y eso se publica")
        self.assertEqual(p.clases, ())

    def test_su_commit_ya_esta_en_el_tronco(self) -> None:
        """Sin esto el estado sería una etiqueta: la rama no aporta ninguna ruta."""
        self.assertEqual(
            _git(self.raiz, "diff", "--name-only", "main...ya-fundida"), "", "nada que aterrizar"
        )
        self.assertEqual(
            _git(self.raiz, "rev-list", "--count", "main..ya-fundida").strip(), "0"
        )


class ElNombreSeQuedaCorto(Sujeto):
    """La mitad que se refutó: por nombres, esta pareja parece libre y no lo está."""

    def test_los_nombres_no_se_cortan_y_la_clase_si(self) -> None:
        base = "main~1"
        de_rama = set(_git(self.raiz, "diff", "--name-only", f"{base}..toca-viejo").split())
        de_tronco = set(_git(self.raiz, "diff", "--name-only", f"{base}..main").split())
        self.assertEqual(de_rama & de_tronco, set(), "por nombres: disjunto ⇒ falso LIBRE")
        self.assertEqual(self.prescripciones()["toca-viejo"].estado, B.REBASAR_CON_RIESGO)


def _replay(ruta: str, tronco: str, ref: str) -> tuple[str, ...]:
    """Rutas que un `rebase --rebase-merges` deja en conflicto, medido en una copia.

    El oráculo de `rutas_en_conflicto` es un merge a tres bandas y **no ve** este caso:
    con el `merge-base` como base, la rama no cambió nada respecto a ella. El conflicto
    sólo aparece al re-ejecutar el merge que la rama guarda, y eso pide un rebase de verdad.
    """
    import shutil

    copia = tempfile.mkdtemp(prefix="mlg-replay-")
    destino = os.path.join(copia, "repo")
    shutil.copytree(ruta, destino, symlinks=True)
    try:
        subprocess.run(
            ["git", "-C", destino, "-c", "rerere.enabled=false", "rebase", "--rebase-merges",
             tronco, ref],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GIT_EDITOR": "true"},
        )
        salida = subprocess.run(
            ["git", "-C", destino, "diff", "--name-only", "--diff-filter=U"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return tuple(sorted(linea for linea in salida.splitlines() if linea.strip()))
    finally:
        shutil.rmtree(copia, ignore_errors=True)


class SujetoConMergeInterno(unittest.TestCase):
    """La rama fundió el tronco resolviendo a mano: la resolución vive en el árbol del merge.

    Reproduce en miniatura `psf/requests` `pr/7065` (merge `fe0853c6`, base `6f66281a`):
    clases disjuntas —la rama toca `a.py`, el tronco `z.py`— y aun así el replay para. La
    base efectiva de un commit que la rama hizo **antes** de fundir el tronco es anterior
    al `merge-base`, y el conflicto cae en una ruta que ninguna de las dos listas netas
    publica como común. `rebase.py` no conserva la resolución: la re-ejecuta y choca.
    """

    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-merge-")
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("init", "-q", "-b", "main")
        g("config", "user.email", "sonda@ejemplo")
        g("config", "user.name", "sonda")
        for nombre in ("a.py", "w.py", "z.py"):
            self._escribir(nombre, CUERPO)
        g("add", "-A")
        g("commit", "-qm", "F base")
        g("branch", "con-merge")
        g("branch", "lineal")

        self._escribir("a.py", CUERPO.replace("linea_5 = 5", "linea_5 = 500"))
        g("commit", "-qam", "tronco: a.py linea 5")

        g("checkout", "-q", "con-merge")
        self._escribir("a.py", CUERPO.replace("linea_5 = 5", "linea_5 = 55"))
        g("commit", "-qam", "rama: a.py linea 5")
        subprocess.run(
            ["git", "-C", self.raiz, "merge", "main"], capture_output=True, text=True, check=False
        )
        self._escribir("a.py", CUERPO.replace("linea_5 = 5", "linea_5 = 5555"))
        g("add", "-A")
        g("commit", "-qm", "Merge branch 'main' into con-merge")

        g("checkout", "-q", "lineal")
        self._escribir("w.py", CUERPO.replace("linea_5 = 5", "linea_5 = 77"))
        g("commit", "-qam", "rama lineal: w.py linea 5")

        g("checkout", "-q", "main")
        self._escribir("z.py", CUERPO.replace("linea_30 = 30", "linea_30 = 3030"))
        g("commit", "-qam", "tronco: z.py linea 30")

    def tearDown(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _escribir(self, nombre: str, texto: str) -> None:
        with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
            f.write(texto)

    def prescripciones(self) -> dict[str, B.Prescripcion]:
        return {p.ref: p for p in B.prescribir(self.raiz, "main", ["con-merge", "lineal"])}

    def test_las_clases_netas_estan_disjuntas(self) -> None:
        """Si no lo estuvieran, el caso no probaría nada: `CON_RIESGO` ya lo habría cazado."""
        base = _git(self.raiz, "merge-base", "main", "con-merge").strip()
        de_rama = set(_git(self.raiz, "diff", "--name-only", f"{base}..con-merge").split())
        de_tronco = set(_git(self.raiz, "diff", "--name-only", f"{base}..main").split())
        self.assertEqual(de_rama, {"a.py"})
        self.assertEqual(de_tronco, {"z.py"})

    def test_el_merge_interno_quita_la_prueba(self) -> None:
        p = self.prescripciones()["con-merge"]
        self.assertEqual(p.estado, B.REBASAR_CON_MERGE_INTERNO)
        self.assertEqual(p.merges, 1)
        self.assertEqual(p.clases, (), "ninguna clase común: no se prueba nada")
        self.assertEqual(p.riesgos, ("a.py",), "lo que la rama toca, para el operador")
        self.assertFalse(p.libre)

    def test_el_replay_choca_y_lo_hace_en_el_merge(self) -> None:
        self.assertEqual(_replay(self.raiz, "main", "con-merge"), ("a.py",))

    def test_sin_merge_la_misma_estructura_sigue_siendo_libre(self) -> None:
        """Control negativo: lo que quita la prueba es el merge, no estar atrás."""
        p = self.prescripciones()["lineal"]
        self.assertEqual(p.estado, B.REBASAR_LIBRE)
        self.assertEqual(p.merges, 0)
        self.assertEqual(_replay(self.raiz, "main", "lineal"), ())


class ResumenYTexto(unittest.TestCase):
    def test_el_resumen_cuenta_las_cinco_clases(self) -> None:
        casos = [
            B.Prescripcion("a", 0, B.AL_DIA),
            B.Prescripcion("b", 3, B.REBASAR_LIBRE),
            B.Prescripcion("c", 9, B.REBASAR_CON_RIESGO, ("x.py",), ("x.py",)),
            B.Prescripcion("d", 40, B.SIN_TRABAJO),
            B.Prescripcion("e", 7, B.REBASAR_CON_MERGE_INTERNO, (), ("y.py",), 1),
        ]
        self.assertEqual(
            B.resumen(casos),
            {
                B.AL_DIA: 1,
                B.REBASAR_LIBRE: 1,
                B.REBASAR_CON_RIESGO: 1,
                B.SIN_TRABAJO: 1,
                B.REBASAR_CON_MERGE_INTERNO: 1,
            },
        )
        texto = "\n".join(B.texto(casos))
        self.assertIn("rebase sin riesgo textual medible", texto)
        self.assertIn("x.py", texto)
        self.assertIn("y.py", texto)
        self.assertIn("no piden aterrizaje ni rebase", texto)
        self.assertIn("1 merge(s) interno(s)", texto)
        self.assertIn("y.py", texto)

    def test_sin_ramas_fundidas_no_hay_linea_de_sobra(self) -> None:
        casos = [B.Prescripcion("b", 3, B.REBASAR_LIBRE)]
        self.assertEqual(B.resumen(casos)[B.SIN_TRABAJO], 0)
        self.assertEqual(B.resumen(casos)[B.REBASAR_CON_MERGE_INTERNO], 0)
        texto = "\n".join(B.texto(casos))
        self.assertNotIn("no piden aterrizaje", texto)
        self.assertNotIn("merge(s) interno(s)", texto)

    def test_sin_ramas_no_hay_seccion(self) -> None:
        self.assertEqual(B.texto([]), [])


class LaCopiaNoSePagaPorDefecto(unittest.TestCase):
    """`--find-copies-harder` cuesta 32× y no compró ni una ruta.

    Medido el 25-Nov-2026 sobre las 155 ramas vivas del corpus: 3 283 ms frente a 101 ms
    por diff, **0 de 137 veredictos** cambiados, y rebasando de verdad las 22 ramas cuyas
    clases se estrechan, **0 de las 67 rutas** en conflicto salían sólo de la cota ancha.
    El flag se queda como opt-in, y estos tests fijan que se pueda pedir: la salida
    estrecha es subconjunto estricto de la ancha, no un reemplazo silencioso.
    """

    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-copias-")
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("init", "-q", "-b", "main")
        g("config", "user.email", "sonda@ejemplo")
        g("config", "user.name", "sonda")
        with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO)
        g("add", "-A")
        g("commit", "-qm", "base")
        # La rama **copia** `a.py`, que el tronco nunca toca. Sólo `--find-copies-harder`
        # ve la copia: con `-M` a secas el archivo nuevo entra como adición simple.
        g("checkout", "-q", "-b", "copia")
        with open(os.path.join(self.raiz, "copia.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO)
        g("add", "-A")
        g("commit", "-qm", "rama: copia a.py sin tocarlo")
        g("checkout", "-q", "main")
        with open(os.path.join(self.raiz, "z.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO)
        g("add", "-A")
        g("commit", "-qm", "tronco: avanza por otro lado")

    def tearDown(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _prescribir(self, **kw) -> B.Prescripcion:
        return B.prescribir(self.raiz, "main", ["copia"], **kw)[0]

    def test_por_defecto_no_se_pide_la_copia_hardera(self) -> None:
        vistas: list[tuple[str, ...]] = []
        original = R.git

        def espia(repo: str, *args: str) -> str:
            if args and args[0] == "diff":
                vistas.append(args)
            return original(repo, *args)

        R.git = espia  # type: ignore[assignment]
        try:
            self._prescribir()
        finally:
            R.git = original  # type: ignore[assignment]
        self.assertTrue(vistas, "el sujeto tiene que producir diffs o el test es vacuo")
        for args in vistas:
            self.assertNotIn("--find-copies-harder", args)
            self.assertIn("-M", args, "sin -M los renombrados dejan de ser aristas de identidad")

    def test_pedirla_la_pide(self) -> None:
        vistas: list[tuple[str, ...]] = []
        original = R.git

        def espia(repo: str, *args: str) -> str:
            if args and args[0] == "diff":
                vistas.append(args)
            return original(repo, *args)

        R.git = espia  # type: ignore[assignment]
        try:
            self._prescribir(copias=True)
        finally:
            R.git = original  # type: ignore[assignment]
        self.assertTrue(vistas)
        for args in vistas:
            self.assertIn("--find-copies-harder", args)

    def test_la_cota_ancha_contiene_a_la_estrecha(self) -> None:
        estrecha = set(self._prescribir().clases)
        ancha = set(self._prescribir(copias=True).clases)
        self.assertTrue(estrecha <= ancha, f"{estrecha - ancha} saldría al pedirla: no es cota")
        self.assertIn("a.py", ancha, "la fuente de la copia entra en la clase ancha")
        self.assertNotIn("a.py", estrecha, "y por eso el default es estrictamente más barato")


class LasDistanciasSonUnaSolaLlamada(unittest.TestCase):
    """`rev-list --left-right --count` publica las dos cuentas que antes pedían dos walks.

    Dos `rev-list --count` cuestan 228 ms y una sola 57 ms sobre el corpus (medido
    25-Nov-2026); la salida es el mismo par campo a campo, y aquí se fija contra las dos
    llamadas de referencia en vez de contra el reloj.
    """

    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-distancias-")
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("init", "-q", "-b", "main")
        g("config", "user.email", "sonda@ejemplo")
        g("config", "user.name", "sonda")
        with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO)
        g("add", "-A")
        g("commit", "-qm", "base")
        g("checkout", "-q", "-b", "atrasada")
        for i in range(2):
            with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
                f.write(CUERPO + f"propio_{i} = {i}\n")
            g("commit", "-qam", f"rama {i}")
        g("checkout", "-q", "main")
        for i in range(3):
            with open(os.path.join(self.raiz, "z.py"), "w", encoding="utf-8") as f:
                f.write(CUERPO + f"tronco_{i} = {i}\n")
            g("add", "-A")
            g("commit", "-qm", f"tronco {i}")

    def tearDown(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)

    def test_coincide_con_las_dos_llamadas_de_referencia(self) -> None:
        atras, adelante = B._distancias(self.raiz, "main", "atrasada")
        self.assertEqual(
            (atras, adelante),
            (
                int(_git(self.raiz, "rev-list", "--count", "atrasada..main").strip()),
                int(_git(self.raiz, "rev-list", "--count", "main..atrasada").strip()),
            ),
        )
        self.assertEqual((atras, adelante), (3, 2), "el sujeto tiene que discriminar los ejes")
        self.assertEqual(B._distancias(self.raiz, "main", "main"), (0, 0))


class LaCLILoPublica(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-rebase-cli-")
        _git(self.raiz, "init", "-q", "-b", "main")
        _git(self.raiz, "config", "user.email", "sonda@ejemplo")
        _git(self.raiz, "config", "user.name", "sonda")
        with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO)
        _git(self.raiz, "add", "-A")
        _git(self.raiz, "commit", "-qm", "base")
        _git(self.raiz, "checkout", "-q", "-b", "otra")
        with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO.replace("linea_1 = 1", "linea_1 = 11"))
        _git(self.raiz, "commit", "-qam", "rama")
        _git(self.raiz, "checkout", "-q", "main")
        with open(os.path.join(self.raiz, "a.py"), "w", encoding="utf-8") as f:
            f.write(CUERPO.replace("linea_2 = 2", "linea_2 = 22"))
        _git(self.raiz, "commit", "-qam", "tronco")
        _git(self.raiz, "checkout", "-q", "-b", "fresca", "main")

    def tearDown(self) -> None:
        shutil.rmtree(self.raiz, ignore_errors=True)

    def _corre(self, *args: str) -> subprocess.CompletedProcess:
        entorno = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return subprocess.run(
            [sys.executable, "-m", "merge_lattice_governor", "--repo", self.raiz, *args],
            capture_output=True, text=True, env=entorno, check=False,
        )

    def test_json_sin_pedirla_es_null_y_con_pedirla_es_medida(self) -> None:
        sin = json.loads(self._corre("--base", "main", "--sin-plan",
                                     "--ref", "otra", "--ref", "fresca", "--json").stdout)
        self.assertIsNone(sin["prescripcion"], "null es «no pedido», no «sin acto»")
        con = json.loads(self._corre("--base", "main", "--sin-plan", "--sin-parejas",
                                     "--ref", "otra", "--prescribir", "--json").stdout)
        self.assertEqual(con["prescripcion"][0]["estado"], B.REBASAR_CON_RIESGO)
        self.assertEqual(con["prescripcion"][0]["riesgos"], ["a.py"])

    def test_la_seccion_sale_en_texto(self) -> None:
        out = self._corre("--base", "main", "--sin-plan", "--sin-parejas", "--ref", "otra",
                          "--prescribir").stdout
        self.assertIn("PRESCRIPCIÓN", out)
        self.assertIn("rebase con 1 archivo(s) en juego", out)

    def test_prescribir_sin_cubeta_no_exige_cubeta(self) -> None:
        proc = self._corre("--base", "main", "--ref", "otra", "--ref", "fresca", "--prescribir")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("holgura-inicial", proc.stderr)
        self.assertIn("PRESCRIPCIÓN", proc.stdout)

    def test_sin_prescripcion_la_cubeta_sigue_siendo_obligatoria(self) -> None:
        proc = self._corre("--base", "main", "--ref", "otra", "--ref", "fresca")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--holgura-inicial", proc.stderr)


if __name__ == "__main__":
    unittest.main()
