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

        g("checkout", "-q", "-b", "al-dia")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.raiz, ignore_errors=True)

    def _escribir(self, nombre: str, texto: str) -> None:
        with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
            f.write(texto)

    def prescripciones(self) -> dict[str, B.Prescripcion]:
        return {p.ref: p for p in B.prescribir(self.raiz, "main", ["toca-viejo", "toca-otro", "al-dia"])}


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


class ElNombreSeQuedaCorto(Sujeto):
    """La mitad que se refutó: por nombres, esta pareja parece libre y no lo está."""

    def test_los_nombres_no_se_cortan_y_la_clase_si(self) -> None:
        base = "main~1"
        de_rama = set(_git(self.raiz, "diff", "--name-only", f"{base}..toca-viejo").split())
        de_tronco = set(_git(self.raiz, "diff", "--name-only", f"{base}..main").split())
        self.assertEqual(de_rama & de_tronco, set(), "por nombres: disjunto ⇒ falso LIBRE")
        self.assertEqual(self.prescripciones()["toca-viejo"].estado, B.REBASAR_CON_RIESGO)


class ResumenYTexto(unittest.TestCase):
    def test_el_resumen_cuenta_las_tres_clases(self) -> None:
        casos = [
            B.Prescripcion("a", 0, B.AL_DIA),
            B.Prescripcion("b", 3, B.REBASAR_LIBRE),
            B.Prescripcion("c", 9, B.REBASAR_CON_RIESGO, ("x.py",), ("x.py",)),
        ]
        self.assertEqual(B.resumen(casos), {B.AL_DIA: 1, B.REBASAR_LIBRE: 1, B.REBASAR_CON_RIESGO: 1})
        texto = "\n".join(B.texto(casos))
        self.assertIn("rebase sin riesgo textual medible", texto)
        self.assertIn("x.py", texto)

    def test_sin_ramas_no_hay_seccion(self) -> None:
        self.assertEqual(B.texto([]), [])


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
        import shutil

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


if __name__ == "__main__":
    unittest.main()
