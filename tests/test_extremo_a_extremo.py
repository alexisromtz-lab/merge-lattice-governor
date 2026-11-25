import json
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout

from merge_lattice_governor.cli import main

APP = "\n".join(f"v{i} = {i}" for i in range(60)) + "\n"


def _suite_base():
    lineas = ["import unittest", "", "", "class Suite(unittest.TestCase):"]
    for i in range(101, 161):
        lineas.append(f"    def test_{i}_m{i:03d}(self):")
        lineas.append(f"        self.assertEqual({i}, {i})")
    return lineas


def _suite_con(ancla, nuevas):
    lineas = _suite_base()
    posicion = lineas.index(ancla) + 2
    return "\n".join(lineas[:posicion] + nuevas + lineas[posicion:]) + "\n"


ALFA = ["    def test_35_alfa(self):", "        self.assertTrue(True)"]
BETA = ["    def test_35_beta(self):", "        self.assertTrue(True)"]


class RepoDePrueba:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "prueba@ejemplo.mx")
        self._git("config", "user.name", "prueba")
        self._git("config", "commit.gpgsign", "false")
        self._escribir("app.py", APP)
        self._escribir("tests/test_suite.py", "\n".join(_suite_base()) + "\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "base")

    def _git(self, *args):
        proceso = subprocess.run(["git", "-C", self.path, *args], capture_output=True, text=True)
        if proceso.returncode != 0:
            raise AssertionError(f"git {args}: {proceso.stderr}")
        return proceso.stdout

    def _escribir(self, archivo, contenido):
        ruta = pathlib.Path(self.path) / archivo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido)

    def rama(self, nombre, archivo, contenido):
        self._git("checkout", "-q", "-B", nombre, "main")
        self._escribir(archivo, contenido)
        self._git("add", "-A")
        self._git("commit", "-qm", nombre)
        self._git("checkout", "-q", "main")

    def cerrar(self):
        self._tmp.cleanup()


def _corre(repo, *args):
    salida = []
    with redirect_stdout(_Captura(salida)):
        rc = main(["--repo", repo, *args])
    return rc, "".join(salida)


class _Captura:
    def __init__(self, buffer):
        self.buffer = buffer

    def write(self, texto):
        self.buffer.append(texto)

    def flush(self):
        pass


class TestMatrizYPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = RepoDePrueba()
        cls.repo.rama("paga", "app.py", APP + "\n".join(f"w{i} = {i}" for i in range(200)) + "\n")
        cls.repo.rama("limpia", "app.py", APP.replace("v50 = 50", "v50 = 500"))
        cls.repo.rama("choca", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        cls.repo.rama("choca2", "app.py", APP.replace("v0 = 0", "v0 = 999"))
        cls.repo.rama(
            "simbolica_p", "tests/test_suite.py", _suite_con("    def test_102_m102(self):", ALFA)
        )
        cls.repo.rama(
            "simbolica_q", "tests/test_suite.py", _suite_con("    def test_150_m150(self):", BETA)
        )

    @classmethod
    def tearDownClass(cls):
        cls.repo.cerrar()

    def _json(self, *refs, h0="10"):
        args = ["--base", "main", "--holgura-inicial", h0, "--json"]
        for ref in refs:
            args += ["--ref", ref]
        rc, salida = _corre(self.repo.path, *args)
        return rc, json.loads(salida)

    def test_pareja_limpia_es_rc_0(self):
        rc, datos = self._json("limpia", "paga")
        self.assertEqual(rc, 0)
        self.assertEqual(datos["parejas"][0]["clase"], "CONMUTA_LIMPIO")
        self.assertEqual(datos["plan"]["excluidas"], [])
        self.assertEqual(datos["schema"], "merge-lattice-governor/1")

    def test_la_rama_de_pago_abre_la_banda(self):
        rc, datos = self._json("limpia", "paga")
        masas = {r["ref"]: (r["vivo"], r["arnes"]) for r in datos["ramas"]}
        self.assertEqual(masas["paga"], (200, 0))
        self.assertEqual(masas["limpia"], (0, 0))
        self.assertGreater(datos["plan"]["holgura_final"], datos["holgura_inicial"])

    def test_conflicto_textual_es_rc_1(self):
        rc, datos = self._json("choca", "choca2")
        self.assertEqual(rc, 1)
        pareja = datos["parejas"][0]
        self.assertEqual(pareja["clase"], "CONFLICTO_TEXTUAL")
        self.assertIn("app.py", pareja["textual"])

    def test_colision_simbolica_es_rc_1_sin_conflicto_textual(self):
        rc, datos = self._json("simbolica_p", "simbolica_q")
        self.assertEqual(rc, 1)
        pareja = datos["parejas"][0]
        self.assertEqual(pareja["textual"], [])
        self.assertEqual(pareja["clase"], "COLISION_SIMBOLICA_AST")
        self.assertTrue(pareja["simbolica"])
        self.assertEqual(datos["plan"]["excluidas"], [])

    def test_las_dos_ramas_de_test_se_clasifican_como_arnes(self):
        _, datos = self._json("simbolica_p", "simbolica_q")
        for rama in datos["ramas"]:
            self.assertEqual((rama["arnes"], rama["vivo"]), (2, 0), rama)

    def test_ref_invalida_es_rc_2(self):
        rc, _ = _corre(self.repo.path, "--base", "main", "--holgura-inicial", "10", "--ref", "no-existe")
        self.assertEqual(rc, 2)

    def test_sin_holgura_inicial_es_rc_2(self):
        rc, _ = _corre(self.repo.path, "--base", "main", "--ref", "limpia")
        self.assertEqual(rc, 2)

    def test_sin_ref_es_rc_2(self):
        rc, _ = _corre(self.repo.path, "--base", "main", "--holgura-inicial", "10")
        self.assertEqual(rc, 2)

    def test_texto_emite_plan_ejecutable(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--holgura-inicial", "10",
            "--ref", "limpia", "--ref", "paga", "--sin-parejas",
        )
        self.assertEqual(rc, 0)
        self.assertIn("PLAN EXACTO", salida)
        self.assertIn("OPERAR", salida)
        self.assertIn("git -C", salida)
        self.assertIn("merge --no-ff", salida)


if __name__ == "__main__":
    unittest.main()
