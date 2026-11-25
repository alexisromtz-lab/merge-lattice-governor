import json
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

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
    with redirect_stdout(_Captura(salida)), redirect_stderr(_Captura(salida)):
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

    def test_una_colision_simbolica_saca_una_rama_del_plan(self):
        # El merge entra limpio y Python se queda con un solo metodo: planificar
        # las dos seria el mismo verde falso que la matriz acaba de cerrar.
        _, datos = self._json("simbolica_p", "simbolica_q")
        excluidas = datos["plan"]["excluidas"]
        self.assertEqual(len(excluidas), 1)
        self.assertEqual(len(datos["plan"]["orden"]), 1)
        self.assertNotIn(excluidas[0], datos["plan"]["orden"])

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


class TestTestigoYMatrizSola(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = RepoDePrueba()
        cls.repo.rama(
            "simbolica_p", "tests/test_suite.py", _suite_con("    def test_102_m102(self):", ALFA)
        )
        cls.repo.rama(
            "simbolica_q", "tests/test_suite.py", _suite_con("    def test_150_m150(self):", BETA)
        )
        cls.repo.rama("choca", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        cls.repo.rama("choca2", "app.py", APP.replace("v0 = 0", "v0 = 999"))

    @classmethod
    def tearDownClass(cls):
        cls.repo.cerrar()

    def test_el_testigo_da_archivo_linea_y_rama(self):
        _, datos = self._json("simbolica_p", "simbolica_q")
        testigo = datos["parejas"][0]["simbolica"][0]
        self.assertRegex(
            testigo,
            r"^tests/test_suite\.py:\d+@simbolica_p Suite\.test_35_alfa vs "
            r"tests/test_suite\.py:\d+@simbolica_q Suite\.test_35_beta$",
        )

    def test_la_linea_del_testigo_apunta_al_def_de_verdad(self):
        # Un testigo con la linea equivocada manda al operador a otro sitio.
        _, datos = self._json("simbolica_p", "simbolica_q")
        testigo = datos["parejas"][0]["simbolica"][0]
        for lado in testigo.split(" vs "):
            ruta, resto = lado.split(":", 1)
            linea, ref = resto.split("@", 1)
            ref, _ = ref.split(" ", 1)
            fuente = self.repo._git("show", f"{ref}:{ruta}").splitlines()
            self.assertIn("test_35_", fuente[int(linea) - 1], lado)

    def test_sin_plan_no_exige_holgura(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--sin-plan",
            "--ref", "choca", "--ref", "choca2",
        )
        self.assertEqual(rc, 0, salida)
        self.assertIn("PLAN: NO_MEDIDO", salida)

    def test_sin_plan_es_rc_1_si_hay_colision_simbolica(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--sin-plan",
            "--ref", "simbolica_p", "--ref", "simbolica_q",
        )
        self.assertEqual(rc, 1)
        self.assertIn("COLISION_SIMBOLICA_AST", salida)

    def test_sin_plan_json_no_inventa_un_plan(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--sin-plan", "--json",
            "--ref", "choca", "--ref", "choca2",
        )
        datos = json.loads(salida)
        self.assertIsNone(datos["plan"])
        self.assertEqual(datos["parejas"][0]["clase"], "CONFLICTO_TEXTUAL")

    def test_prioridad_desconocida_es_rc_2(self):
        rc, _ = _corre(
            self.repo.path, "--base", "main", "--holgura-inicial", "10",
            "--ref", "choca", "--prioridad", "no-existe=3",
        )
        self.assertEqual(rc, 2)

    def _json(self, *refs):
        args = ["--base", "main", "--holgura-inicial", "10", "--json"]
        for ref in refs:
            args += ["--ref", ref]
        rc, salida = _corre(self.repo.path, *args)
        return rc, json.loads(salida)


class TestIlegibleYRamaSola(unittest.TestCase):
    """Un archivo que no compila no es un par limpio, y una rama sola no es 0 pares."""

    @classmethod
    def setUpClass(cls):
        cls.repo = RepoDePrueba()
        cls.repo.rama("sana", "tests/test_suite.py", _suite_con("    def test_102_m102(self):", ALFA))
        cls.repo.rama(
            "rota",
            "tests/test_suite.py",
            ("\n".join(_suite_base()) + "\n").replace("import unittest", "import unittest("),
        )
        cls.repo.rama(
            "duplicada",
            "tests/test_dup.py",
            "\n".join(
                [
                    "import unittest",
                    "",
                    "",
                    "class S(unittest.TestCase):",
                    "    def test_06_x(self):",
                    "        pass",
                    "",
                    "    def test_06_y(self):",
                    "        pass",
                    "",
                ]
            ),
        )

    @classmethod
    def tearDownClass(cls):
        cls.repo.cerrar()

    def test_un_archivo_ilegible_no_es_un_par_limpio(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--sin-plan", "--ref", "sana", "--ref", "rota"
        )
        self.assertEqual(rc, 2, salida)
        self.assertIn("NO_MEDIDO 1", salida)
        self.assertIn("tests/test_suite.py: no se puede leer como Python (SyntaxError)", salida)

    def test_un_archivo_ilegible_no_se_declara_limpio_en_json(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--sin-plan", "--json",
            "--ref", "sana", "--ref", "rota",
        )
        datos = json.loads(salida)
        self.assertEqual(rc, 2)
        pareja = datos["parejas"][0]
        self.assertEqual(pareja["clase"], "NO_MEDIDO")
        self.assertEqual(len(pareja["ilegibles"]), 1)
        self.assertEqual(datos["resumen"]["NO_MEDIDO"], 1)

    def test_una_rama_sola_se_audita_y_su_duplicado_es_rc_1(self):
        rc, salida = _corre(self.repo.path, "--base", "main", "--sin-plan", "--ref", "duplicada")
        self.assertEqual(rc, 1, salida)
        self.assertIn("duplicados internos 1 · ilegibles 0", salida)
        testigos = [linea for linea in salida.splitlines() if " vs " in linea]
        self.assertEqual(len(testigos), 1, salida)
        self.assertIn("tests/test_dup.py:", testigos[0])
        self.assertIn("S.test_06_y", testigos[0])
        self.assertIn("S.test_06_x", testigos[0])

    def test_una_rama_sola_sin_duplicados_es_rc_0(self):
        rc, salida = _corre(self.repo.path, "--base", "main", "--sin-plan", "--ref", "sana")
        self.assertEqual(rc, 0, salida)
        self.assertIn("duplicados internos 0 · ilegibles 0", salida)

    def test_una_rama_sola_ilegible_es_rc_2(self):
        rc, salida = _corre(self.repo.path, "--base", "main", "--sin-plan", "--ref", "rota")
        self.assertEqual(rc, 2, salida)
        self.assertIn("ilegibles 1", salida)

    def test_la_matriz_no_acepta_una_sola_rama(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--holgura-inicial", "10", "--ref", "sana"
        )
        self.assertEqual(rc, 2)
        self.assertIn("una matriz de 0 pares no es una matriz limpia", salida)


class TestFormaDelJson(unittest.TestCase):
    """El mismo ``schema`` no admite tres sobres distintos ni claves condicionales.

    Medido en la banca externa: un consumidor que leía ``datos["ilegibles"]`` se
    rompía con KeyError justo cuando no había nada ilegible, y ``ramas`` era una
    lista de cadenas o de objetos según el modo. Ausencia no es cero.
    """

    @classmethod
    def setUpClass(cls):
        cls.repo = RepoDePrueba()
        cls.repo.rama("limpia", "app.py", "X = 1\n")
        cls.repo.rama("paga", "nuevo.py", "Y = 2\n")
        cls.repo.rama("sana", "tests/test_suite.py", _suite_con("    def test_102_m102(self):", ALFA))
        cls.repo.rama(
            "rota",
            "tests/test_suite.py",
            ("\n".join(_suite_base()) + "\n").replace("import unittest", "import unittest("),
        )

    @classmethod
    def tearDownClass(cls):
        cls.repo.cerrar()

    def _json(self, *args):
        rc, salida = _corre(self.repo.path, "--json", *args)
        return rc, json.loads(salida)

    def _los_tres_modos(self):
        plan = self._json("--base", "main", "--holgura-inicial", "10",
                          "--ref", "limpia", "--ref", "paga")[1]
        matriz = self._json("--base", "main", "--sin-plan",
                            "--ref", "limpia", "--ref", "paga")[1]
        sola = self._json("--base", "main", "--sin-plan", "--ref", "limpia")[1]
        return plan, matriz, sola

    def test_los_tres_modos_emiten_el_mismo_sobre(self):
        plan, matriz, sola = self._los_tres_modos()
        self.assertEqual(set(plan), set(matriz), "plan vs matriz sola")
        self.assertEqual(set(plan), set(sola), "plan vs rama sola")
        self.assertEqual({d["schema"] for d in (plan, matriz, sola)},
                         {"merge-lattice-governor/1"})

    def test_ramas_es_una_lista_de_objetos_en_los_tres_modos(self):
        for datos in self._los_tres_modos():
            self.assertTrue(datos["ramas"], datos)
            for rama in datos["ramas"]:
                self.assertIsInstance(rama, dict)
                self.assertIn("ref", rama)
                self.assertIn("arnes", rama)

    def test_ilegibles_es_lista_siempre_y_nombra_la_ruta(self):
        plan, matriz, sola = self._los_tres_modos()
        for datos in (plan, matriz, sola):
            self.assertEqual(datos["ilegibles"], [], datos["criterio"])
        _, con_rota = self._json("--base", "main", "--sin-plan",
                                 "--ref", "sana", "--ref", "rota")
        self.assertEqual(con_rota["ilegibles"], ["tests/test_suite.py"], con_rota["criterio"])

    def test_sin_masa_las_cifras_son_null_y_nunca_cero(self):
        plan, matriz, sola = self._los_tres_modos()
        for datos in (matriz, sola):
            for rama in datos["ramas"]:
                for clave in ("arnes", "vivo", "sim", "delta_holgura"):
                    self.assertIsNone(rama[clave], f"{datos['criterio']}: {clave}")
        for rama in plan["ramas"]:
            self.assertIsInstance(rama["arnes"], int)

    def test_la_rama_sola_conserva_su_hallazgo_y_las_otras_modos_no(self):
        plan, matriz, _ = self._los_tres_modos()
        _, sola = self._json("--base", "main", "--sin-plan", "--ref", "rota")
        self.assertIn("sola", sola)
        self.assertIsNone(plan["sola"])
        self.assertIsNone(matriz["sola"])
        self.assertIsNone(sola["plan"])
        self.assertIsNone(sola["resumen"], "0 pares no es un resumen: es un denominador vacío")


if __name__ == "__main__":
    unittest.main()


class TestDuplicadoIdenticoExtremo(unittest.TestCase):
    """Dos ramas que insertan el mismo test: git no choca, Python no pierde nada.

    Antes del canal ``identico`` esto era ``COLISION_SIMBOLICA_AST`` y RC 1; el
    plan quedaba con 1/2 ramas. El caso real (15 PRs, 26-Nov-2026) fue 75 de 75.
    """

    CUERPO = ["    def test_900_repetido(self):", "        self.assertEqual(2 + 2, 4)"]
    ANCLA = "    def test_101_m101(self):"

    @classmethod
    def setUpClass(cls):
        cls.repo = RepoDePrueba()
        suite = _suite_con(cls.ANCLA, cls.CUERPO)
        cls.repo.rama("mismo_a", "tests/test_suite.py", suite)
        cls.repo.rama("mismo_b", "tests/test_suite.py", suite)

    @classmethod
    def tearDownClass(cls):
        cls.repo.cerrar()

    def test_la_pareja_es_limpia_y_el_duplicado_se_publica(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--holgura-inicial", "10", "--json", "--ref", "mismo_a", "--ref", "mismo_b"
        )
        datos = json.loads(salida)
        self.assertEqual(rc, 0, salida)
        pareja = datos["parejas"][0]
        self.assertEqual(pareja["clase"], "CONMUTA_LIMPIO")
        self.assertEqual(pareja["simbolica"], [])
        self.assertEqual(len(pareja["identicos"]), 1)
        self.assertIn("test_900_repetido", pareja["identicos"][0])
        self.assertEqual(datos["duplicados"]["duplicados_identicos"], 1)
        self.assertEqual(datos["duplicados"]["parejas_con_duplicados_identicos"], 1)
        self.assertEqual(sorted(datos["plan"]["orden"]), ["mismo_a", "mismo_b"])
        self.assertEqual(datos["plan"]["excluidas"], [])

    def test_la_matriz_declara_que_miro(self):
        rc, salida = _corre(
            self.repo.path, "--base", "main", "--holgura-inicial", "10", "--ref", "mismo_a", "--ref", "mismo_b"
        )
        self.assertEqual(rc, 0, salida)
        self.assertIn("DUPLICADOS_IDENTICOS", salida)
        self.assertIn("mirado, no ausente", salida)
