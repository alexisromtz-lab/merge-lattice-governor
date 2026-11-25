import pathlib
import unittest

from merge_lattice_governor.ley import (
    ARNES,
    SIM,
    VIVO,
    Masa,
    clase_de,
)


class TestClasificacion(unittest.TestCase):
    def test_prefijo_de_arnes_gana(self):
        self.assertEqual(clase_de("tools/panel.py"), ARNES)
        self.assertEqual(clase_de("tests/test_x.py"), ARNES)
        self.assertEqual(clase_de(".github/workflows/ci.yml"), ARNES)
        self.assertEqual(clase_de("pre-write-gate/gate.sh"), ARNES)

    def test_simulacion_se_mide_aparte(self):
        self.assertEqual(clase_de("sim/motor.py"), SIM)

    def test_producto_es_lo_demas(self):
        self.assertEqual(clase_de("empresa/ventas.py"), VIVO)

    def test_sin_extension_de_codigo_no_mueve_masa(self):
        for ruta in ("README.md", "crudos/x.json", "showcase/index.html", "notas.txt"):
            self.assertIsNone(clase_de(ruta), ruta)


class TestMasa(unittest.TestCase):
    def test_suma_por_clase(self):
        total = Masa().sumar(ARNES, 10).sumar(VIVO, 20).sumar(SIM, 5)
        self.assertEqual((total.arnes, total.vivo, total.sim), (10, 20, 5))
        self.assertEqual(total.producto, 25)
        self.assertEqual(total.neto, 35)

    def test_adicion_es_conmutativa(self):
        a = Masa(1, 2, 3)
        b = Masa(4, 5, 6)
        self.assertEqual(a + b, b + a)

    def test_clase_desconocida_falla(self):
        with self.assertRaises(ValueError):
            Masa().sumar("otra", 1)


class TestLey(unittest.TestCase):
    def test_pago_con_producto_vivo_abre_el_techo(self):
        # Corredor certificado: 1029 líneas vivas, cero arnés.
        self.assertAlmostEqual(Masa(0, 1029, 0).delta(), 1460.97, places=2)

    def test_arnes_puro_solo_cierra(self):
        self.assertAlmostEqual(Masa(394, 0, 0).delta(), -394.0, places=2)

    def test_simulacion_solo_cobra_la_banda(self):
        self.assertAlmostEqual(Masa(0, 0, 1000).delta(), 50.0, places=2)

    def test_trayectoria_certificada(self):
        holgura = -1020.35
        for masa in (Masa(0, 1029, 0), Masa(98, 0, 0), Masa(145, 0, 0), Masa(151, 0, 0)):
            holgura += masa.delta()
        self.assertAlmostEqual(holgura, 46.62, places=2)


class TestVersion(unittest.TestCase):
    def test_la_version_tiene_una_sola_fuente(self):
        # 0.1.1 se publicó con __init__ en 0.1.0 y pyproject en 0.1.1: dos copias divergieron.
        texto = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
        self.assertIn('dynamic = ["version"]', texto)
        self.assertNotRegex(texto, r'(?m)^version = "')
        self.assertIn('attr = "merge_lattice_governor.__version__"', texto)


if __name__ == "__main__":
    unittest.main()
