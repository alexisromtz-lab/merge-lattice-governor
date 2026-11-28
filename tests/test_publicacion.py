"""La publicación medida: la guarda de etiqueta y el flujo que la invoca.

`pypa/gh-action-pypi-publish` no se puede ejercitar desde un test —publicar
de verdad es el acto que se quiere impedir—, así que lo que se mide es lo que
sí decide: la guarda, en los dos sentidos, y la forma del flujo (sólo tags,
OIDC, guarda antes de subir). El resto es una frontera declarada.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

from merge_lattice_governor import __version__

RAIZ = pathlib.Path(__file__).resolve().parent.parent
GUARDA = RAIZ / "scripts" / "verificar_etiqueta.py"
FLUJO = RAIZ / ".github" / "workflows" / "publicar.yml"


def corre(*args: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(GUARDA), *args],
        capture_output=True, text=True, cwd=str(RAIZ),
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    return r.returncode, (r.stdout + r.stderr).strip()


class GuardaDeEtiqueta(unittest.TestCase):
    def test_la_etiqueta_que_cuadra_pasa(self) -> None:
        rc, salida = corre(f"v{__version__}")
        self.assertEqual(0, rc, salida)

    def test_la_etiqueta_que_no_cuadra_para(self) -> None:
        for mala in ("v9.9.9", __version__, f"v{__version__}-rc1"):
            with self.subTest(etiqueta=mala):
                rc, salida = corre(mala)
                self.assertEqual(1, rc, salida)

    def test_sin_etiqueta_no_hay_publicacion(self) -> None:
        rc, salida = corre()
        self.assertEqual(2, rc, salida)


class FormaDelFlujo(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = FLUJO.read_text(encoding="utf-8")

    def test_solo_dispara_en_etiquetas(self) -> None:
        self.assertIn('tags: ["v*"]', self.texto)
        self.assertNotIn("branches:", self.texto)

    def test_la_guarda_corre_antes_de_construir_y_subir(self) -> None:
        guarda = self.texto.index("verificar_etiqueta.py")
        construir = self.texto.index("python -m build")
        subir = self.texto.index("pypa/gh-action-pypi-publish")
        self.assertLess(guarda, construir)
        self.assertLess(construir, subir)

    def test_publica_por_oidc_sin_token_estatico(self) -> None:
        self.assertIn("id-token: write", self.texto)
        self.assertIn("environment: pypi", self.texto)
        for prohibido in ("PYPI_API_TOKEN", "password:", "TWINE_PASSWORD"):
            self.assertNotIn(prohibido, self.texto)
