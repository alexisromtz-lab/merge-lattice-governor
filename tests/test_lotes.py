"""Lotes: la coloración del grafo de choque promete una corrida de CI sin conflictos.

Dos mitades, como en el resto del paquete:

1. La mitad **algebraica**, sin git: `choques`, `colorear` y `cota_inferior` sobre
   soportes fabricados. Un color nunca contiene dos ramas adyacentes, la cota
   inferior es una clique y la voraz la respeta.
2. La mitad **de acto**: un repositorio de verdad con tres ramas disjuntas y una
   que comparte archivo. Se integra el primer lote de verdad —`git merge` de sus
   ramas, una sobre otra— y tiene que salir limpio; el lote declarado seguro no
   puede producir un conflicto.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from merge_lattice_governor import lotes as L  # noqa: E402

CUERPO = "\n".join(f"linea_{i} = {i}" for i in range(40)) + "\n"


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True)
    return out.stdout


class ElGrafoDeChoque(unittest.TestCase):
    def test_soporte_disjunto_es_seguro_y_el_comun_no(self) -> None:
        sop = {"a": ("x.py", "y.py"), "b": ("z.py",), "c": ("y.py", "w.py")}
        grafo = L.choques(sop)
        self.assertEqual(grafo["a"], {"c"})
        self.assertEqual(grafo["b"], set())

    def test_un_color_no_contiene_dos_ramas_adyacentes(self) -> None:
        sop = {f"r{i}": (f"{i}.py", "comun.py") for i in range(5)}
        sop["solo"] = ("unico.py",)
        grafo = L.choques(sop)
        for grupo in L.colorear(grafo):
            for i, a in enumerate(grupo):
                for b in grupo[i + 1 :]:
                    self.assertNotIn(b, grafo[a], f"{a} y {b} comparten archivo en el mismo lote")

    def test_la_cota_inferior_es_una_clique(self) -> None:
        sop = {"a": ("f.py",), "b": ("f.py",), "c": ("f.py",), "d": ("g.py",)}
        self.assertEqual(L.cota_inferior(sop), 3)

    def test_ramas_todas_disjuntas_caben_en_un_lote(self) -> None:
        sop = {"a": ("a.py",), "b": ("b.py",), "c": ("c.py",)}
        grupos = L.colorear(L.choques(sop))
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0], ("a", "b", "c"))

    def test_ramas_que_comparten_archivo_no_caben_juntas(self) -> None:
        sop = {"a": ("f.py",), "b": ("f.py",)}
        grupos = L.colorear(L.choques(sop))
        self.assertEqual(len(grupos), 2)

    def test_archivo_frente_a_directorio_tambien_es_arista(self) -> None:
        """`dw` y `dw/inner.txt` no comparten ruta y chocan: no caben en el mismo lote."""
        sop = {"a": ("dw",), "b": ("dw/inner.txt",), "c": ("otro.py",)}
        grafo = L.choques(sop)
        self.assertEqual(grafo["a"], {"b"})
        self.assertEqual(grafo["c"], set())
        grupos = L.colorear(grafo)
        for grupo in grupos:
            self.assertFalse({"a", "b"} <= set(grupo))


class ElLoteDeclaradoSeguroIntegraLimpio(unittest.TestCase):
    """El acto, no la predicción: se mergea el lote y se mira si choca."""

    def setUp(self) -> None:
        self.raiz = tempfile.mkdtemp(prefix="mlg-lotes-")
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("init", "-q", "-b", "main")
        g("config", "user.email", "sonda@ejemplo")
        g("config", "user.name", "sonda")
        for nombre in ("a.py", "b.py", "c.py", "d.py"):
            with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
                f.write(CUERPO)
        g("add", "-A")
        g("commit", "-q", "-m", "tronco")

        # tres ramas sobre archivos distintos: lote seguro
        for nombre in ("a.py", "b.py", "c.py"):
            g("checkout", "-q", "-b", f"rama-{nombre[0]}", "main")
            with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as f:
                f.write(CUERPO.replace("linea_0 = 0", f"linea_0 = {nombre!r}"))
            g("commit", "-q", "-am", f"toca {nombre}")

        # dos ramas sobre el mismo archivo: no seguras
        for etiqueta in ("uno", "dos"):
            g("checkout", "-q", "-b", f"choca-{etiqueta}", "main")
            with open(os.path.join(self.raiz, "d.py"), "w", encoding="utf-8") as f:
                f.write(CUERPO.replace("linea_0 = 0", f"linea_0 = {etiqueta!r}"))
            g("commit", "-q", "-am", f"toca d.py desde {etiqueta}")

        g("checkout", "-q", "main")

    def test_el_lote_seguro_se_integra_limpio_y_el_choque_no(self) -> None:
        refs = ["rama-a", "rama-b", "rama-c", "choca-uno", "choca-dos"]
        resultado = L.lotes(self.raiz, "main", refs)

        tres = {"rama-a", "rama-b", "rama-c"}
        seguros = [g for g in resultado.lotes if tres <= set(g)]
        self.assertEqual(len(seguros), 1, f"las tres disjuntas deben caber juntas: {resultado.lotes}")

        for grupo in resultado.lotes:
            self.assertFalse({"choca-uno", "choca-dos"} <= set(grupo), "las que comparten archivo no caben juntas")

        # El acto: integrar el lote declarado seguro, de verdad.
        g = lambda *a: _git(self.raiz, *a)  # noqa: E731
        g("checkout", "-q", "-B", "integracion", "main")
        for rama in seguros[0]:
            salida = subprocess.run(
                ["git", "-C", self.raiz, "merge", "--no-edit", rama],
                capture_output=True, text=True,
            )
            self.assertEqual(salida.returncode, 0, f"{rama} chocó dentro de un lote declarado seguro")

        # La contraprueba: las dos que comparten archivo sí chocan.
        g("checkout", "-q", "-B", "contraprueba", "main")
        g("merge", "--no-edit", "choca-uno")
        choque = subprocess.run(
            ["git", "-C", self.raiz, "merge", "--no-edit", "choca-dos"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(choque.returncode, 0, "el par declarado no seguro no chocó: la cota no mide nada")


if __name__ == "__main__":
    unittest.main()
