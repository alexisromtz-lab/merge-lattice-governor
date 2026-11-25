import unittest

from merge_lattice_governor.sombra import colisiones, metodos

FUENTE = '''
import unittest


class Suite(unittest.TestCase):
    def test_1_uno(self):
        pass

    def test_35_alfa(self):
        self.assertTrue(True)

    class Anidada(unittest.TestCase):
        def test_35_dentro(self):
            pass


class Otra(unittest.TestCase):
    def test_35_otra(self):
        pass

    async def test_7_asincrono(self):
        pass


def test_9_suelto():
    pass
'''


class TestExtraccion(unittest.TestCase):
    def test_ordinal_sale_del_nombre(self):
        encontrados = {m.nombre: m.ordinal for m in metodos(FUENTE)}
        self.assertEqual(encontrados["test_1_uno"], 1)
        self.assertEqual(encontrados["test_35_alfa"], 35)
        self.assertEqual(encontrados["test_7_asincrono"], 7)
        self.assertEqual(encontrados["test_9_suelto"], 9)

    def test_clase_anidada_lleva_nombre_punteado(self):
        clases = {m.nombre: m.clase for m in metodos(FUENTE)}
        self.assertEqual(clases["test_35_dentro"], "Suite.Anidada")
        self.assertEqual(clases["test_35_alfa"], "Suite")
        self.assertEqual(clases["test_9_suelto"], "")

    def test_archivo_que_no_compila_no_explota(self):
        self.assertEqual(metodos("def roto(:\n"), [])


class TestColisiones(unittest.TestCase):
    def test_misma_clase_mismo_ordinal_distinto_nombre_es_rojo(self):
        a = metodos("class S:\n    def test_35_alfa(self):\n        pass\n")
        b = metodos("class S:\n    def test_35_beta(self):\n        pass\n")
        self.assertEqual(len(colisiones(a, b)), 1)

    def test_mismo_nombre_es_el_mismo_test(self):
        a = metodos("class S:\n    def test_35_alfa(self):\n        pass\n")
        self.assertEqual(colisiones(a, a), [])

    def test_distinta_clase_no_se_pisa(self):
        a = metodos("class A:\n    def test_35_x(self):\n        pass\n")
        b = metodos("class B:\n    def test_35_y(self):\n        pass\n")
        self.assertEqual(colisiones(a, b), [])

    def test_distinto_ordinal_no_colisiona(self):
        a = metodos("class S:\n    def test_35_x(self):\n        pass\n")
        b = metodos("class S:\n    def test_36_y(self):\n        pass\n")
        self.assertEqual(colisiones(a, b), [])


if __name__ == "__main__":
    unittest.main()
