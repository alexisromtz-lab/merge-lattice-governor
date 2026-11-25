import unittest

from merge_lattice_governor.sombra import colisiones, metodos, nuevos

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

    def test_por_defecto_el_mismo_nombre_no_dispara(self):
        # Compatibilidad del contrato: sin la marca, la regla del nombre no corre.
        a = metodos("class S:\n    def test_35_alfa(self):\n        pass\n")
        self.assertEqual(colisiones(a, a), [])

    def test_mismo_nombre_en_la_misma_clase_es_colision_cuando_se_pide(self):
        # Lo que merge-tree no ve: dos ramas insertan el mismo def y una gana.
        a = metodos("class S:\n    def test_algo(self):\n        pass\n")
        b = metodos("class S:\n    def test_algo(self):\n        return 2\n")
        self.assertEqual(colisiones(a, b, incluir_mismo_nombre=True), [(a[0], b[0])])

    def test_un_metodo_sin_ordinal_tambien_se_extrae(self):
        self.assertEqual(len(metodos("class S:\n    def test_algo(self):\n        pass\n")), 1)

    def test_lo_heredado_de_la_base_no_es_colision_de_la_pareja(self):
        base = metodos("class S:\n    def test_algo(self):\n        pass\n")
        a = metodos("class S:\n    def test_algo(self):\n        pass\n\n    def test_40_a(self):\n        pass\n")
        b = metodos("class S:\n    def test_algo(self):\n        pass\n\n    def test_40_b(self):\n        pass\n")
        # Sin base: el heredado también dispara (ruido).
        self.assertEqual(len(colisiones(a, b, incluir_mismo_nombre=True)), 2)
        self.assertEqual(colisiones(nuevos(base, a), nuevos(base, b), incluir_mismo_nombre=True), [(nuevos(base, a)[0], nuevos(base, b)[0])])

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
