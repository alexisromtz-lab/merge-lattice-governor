"""La acción compuesta: el RC del gobernador tiene que ser el RC del paso.

Un `action.yml` que publica el RC y sale con 0 convierte un plan insolvente en un check
verde: el mismo falso verde que el paquete mide en el eje de los merges. Estas pruebas
corren el cuerpo real de la acción (`scripts/accion.sh`) sin GitHub, y comprueban que
`action.yml` declara exactamente las entradas que ese cuerpo lee.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ACCION = RAIZ / "scripts" / "accion.sh"
APP = "\n".join(f"v{i} = {i}" for i in range(60)) + "\n"


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


class Repo(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name) / "sujeto"
        self.path.mkdir()
        _git(self.path, "init", "-q", "-b", "main")
        _git(self.path, "config", "user.email", "t@t")
        _git(self.path, "config", "user.name", "t")
        (self.path / "app.py").write_text(APP)
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-qm", "base")
        for rama, linea in (("a", 0), ("b", 20), ("c", 40)):
            _git(self.path, "checkout", "-q", "-b", rama, "main")
            actual = (self.path / "app.py").read_text()
            (self.path / "app.py").write_text(
                actual.replace(f"v{linea} = {linea}", f"v{linea} = {linea}00")
            )
            (self.path / f"nota_{rama}.py").write_text(f"# {rama}\n")
            _git(self.path, "add", "-A")
            _git(self.path, "commit", "-qm", rama)
        _git(self.path, "checkout", "-q", "main")

        # El cuerpo de la acción llama al comando instalado; aquí se le da un shim.
        self.bin = pathlib.Path(self._tmp.name) / "bin"
        self.bin.mkdir()
        shim = self.bin / "merge-lattice-governor"
        shim.write_text(
            "#!/bin/sh\nexec \"%s\" -m merge_lattice_governor \"$@\"\n" % sys.executable
        )
        shim.chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def corre(self, **entorno: str) -> subprocess.CompletedProcess:
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "GITHUB_WORKSPACE": str(self.path),
            "INPUT_BASE": "main",
            "INPUT_HOLGURA": "0",
            "INPUT_REFS": "a,b,c",
        }
        env.update(entorno)
        env = {k: v for k, v in env.items() if v != ""}
        return subprocess.run(
            ["bash", str(ACCION)], env=env, capture_output=True, text=True, check=False
        )

    def test_plan_solvente_sale_cero_y_ordena_las_tres(self) -> None:
        proc = self.corre()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PLAN EXACTO · 3/3 integradas", proc.stdout)

    def test_plan_insolvente_sale_uno_para_que_el_check_no_finja_verde(self) -> None:
        proc = self.corre(INPUT_HOLGURA="-100")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_sin_holgura_es_rc_dos_y_lo_dice(self) -> None:
        proc = self.corre(INPUT_HOLGURA="")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("falta el input holgura-inicial", proc.stderr)

    def test_sin_refs_tambien_es_rc_dos(self) -> None:
        proc = self.corre(INPUT_REFS="")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("falta el input refs", proc.stderr)

    def test_salida_json_escribe_el_informe_y_conserva_el_rc(self) -> None:
        destino = pathlib.Path(self._tmp.name) / "artefactos" / "plan.json"
        proc = self.corre(INPUT_SALIDA_JSON=str(destino))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        datos = json.loads(destino.read_text())
        self.assertEqual(len(datos["ramas"]), 3)
        self.assertEqual(len(datos["plan"]["orden"]), 3)
        self.assertTrue(datos["plan"]["exacto"])

    def test_los_refs_admiten_coma_y_espacio(self) -> None:
        por_coma = self.corre(INPUT_REFS="a,b,c")
        por_espacio = self.corre(INPUT_REFS="a b c")
        self.assertEqual(por_coma.returncode, 0, por_coma.stderr)
        self.assertEqual(por_espacio.returncode, 0, por_espacio.stderr)


class DeclaracionDeLaAccion(unittest.TestCase):
    """`action.yml` y el cuerpo no pueden declarar contratos distintos."""

    def setUp(self) -> None:
        import yaml

        self.accion = yaml.safe_load((RAIZ / "action.yml").read_text())

    def test_declara_las_entradas_que_el_cuerpo_lee(self) -> None:
        entradas = set(self.accion["inputs"])
        esperadas = {"holgura-inicial", "refs", "base", "repo", "ratio", "banda",
                     "argumentos", "salida-json"}
        self.assertEqual(entradas, esperadas)

    def test_el_paso_del_plan_sale_con_el_rc_del_gobernador(self) -> None:
        pasos = self.accion["runs"]["steps"]
        plan = [p for p in pasos if p.get("id") == "plan"]
        self.assertEqual(len(plan), 1, "sin id=plan, outputs.rc no tiene de dónde leer")
        guion = plan[0]["run"]
        self.assertIn("exit $rc", guion, "publicar el RC y salir con 0 es un verde falso")
        self.assertEqual(self.accion["outputs"]["rc"]["value"], "${{ steps.plan.outputs.rc }}")

    def test_instala_el_paquete_de_esta_accion_y_no_de_un_remoto(self) -> None:
        instalacion = [p for p in self.accion["runs"]["steps"] if "pip install" in p.get("run", "")]
        self.assertEqual(len(instalacion), 1)
        self.assertIn("github.action_path", instalacion[0]["run"])
        self.assertNotIn("git+https", instalacion[0]["run"])


if __name__ == "__main__":
    unittest.main()
