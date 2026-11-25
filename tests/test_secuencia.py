import unittest

from merge_lattice_governor.ley import Masa
from merge_lattice_governor.secuencia import Rama, planificar


def _ramas(*masas):
    return [Rama(f"r{i}", masa) for i, masa in enumerate(masas, start=1)]


class TestCorredorCertificado(unittest.TestCase):
    """Las masas y la holgura inicial son las medidas sobre el tronco real."""

    H0 = -1020.35

    def _corredor(self):
        return [
            Rama("pago", Masa(0, 1029, 0)),
            Rama("techo-vivo", Masa(98, 0, 0)),
            Rama("orden-b3", Masa(145, 0, 0)),
            Rama("panel-ratio", Masa(151, 0, 0)),
        ]

    def test_integra_las_cuatro(self):
        plan = planificar(self._corredor(), self.H0)
        self.assertTrue(plan.completo)
        self.assertEqual(plan.integradas, 4)
        self.assertAlmostEqual(plan.holgura_final, 46.62, places=2)

    def test_el_pago_va_primero(self):
        plan = planificar(self._corredor(), self.H0)
        self.assertEqual(plan.orden[0], "pago")

    def test_el_orden_canonico_reproduce_el_del_runbook(self):
        plan = planificar(self._corredor(), self.H0)
        self.assertEqual(plan.orden, ("pago", "techo-vivo", "orden-b3", "panel-ratio"))

    def test_cada_prefijo_es_solvente(self):
        plan = planificar(self._corredor(), self.H0)
        self.assertTrue(all(h > 0 for h in plan.trayectoria), plan.trayectoria)

    def test_sin_el_pago_no_entra_nada(self):
        plan = planificar(self._corredor()[1:], self.H0)
        self.assertEqual(plan.integradas, 0)
        self.assertEqual(len(plan.excluidas), 3)


class TestSolvenciaEstricta(unittest.TestCase):
    def test_holgura_cero_no_es_solvencia(self):
        plan = planificar(_ramas(Masa()), 0.0)
        self.assertEqual(plan.integradas, 0)

    def test_holgura_positiva_minima_admite_la_rama_nula(self):
        plan = planificar(_ramas(Masa()), 0.0001)
        self.assertEqual(plan.integradas, 1)

    def test_una_rama_que_cierra_exacto_queda_fuera(self):
        plan = planificar(_ramas(Masa(10, 0, 0)), 10.0)
        self.assertEqual(plan.integradas, 0)
        self.assertEqual(plan.excluidas, ("r1",))


class TestOrden(unittest.TestCase):
    def test_el_orden_canonico_es_el_mas_solvente(self):
        # Para un conjunto fijo, el orden descendente domina a cualquier otro en
        # todos los prefijos a la vez.
        ramas = _ramas(Masa(0, 0, 1000), Masa(25, 0, 0), Masa(10, 0, 0))
        plan = planificar(ramas, 1.0)
        self.assertEqual(plan.orden, ("r1", "r3", "r2"))

    def test_el_orden_importa_aunque_la_suma_no(self):
        # 1000 líneas de simulación valen +50 (sólo banda); dos cierres de 25 no
        # caben desde 1.0 salvo que el que abre vaya primero.
        plan = planificar(_ramas(Masa(0, 0, 1000), Masa(25, 0, 0), Masa(25, 0, 0)), 1.0)
        self.assertTrue(plan.completo, plan.excluidas)
        self.assertEqual(plan.orden[0], "r1", "sin abrir la banda primero, los cierres no caben")

    def test_maximiza_el_numero_integrado(self):
        plan = planificar(_ramas(*(Masa(3, 0, 0) for _ in range(4))), 10.0)
        self.assertEqual(plan.integradas, 3)
        self.assertAlmostEqual(plan.holgura_final, 1.0, places=2)

    def test_es_determinista(self):
        ramas = _ramas(Masa(0, 100, 0), Masa(30, 0, 0), Masa(0, 0, 100))
        self.assertEqual(planificar(ramas, 5.0), planificar(ramas, 5.0))

    def test_vacio_no_falla(self):
        plan = planificar([], 7.0)
        self.assertEqual((plan.orden, plan.holgura_final), ((), 7.0))


class TestCotaGreedy(unittest.TestCase):
    def test_fuera_de_la_cota_declara_que_no_es_exacto(self):
        ramas = [Rama(f"r{i:02d}", Masa(0, 10, 0)) for i in range(20)]
        plan = planificar(ramas, 1.0, maximo_exacto=18)
        self.assertFalse(plan.exacto)
        self.assertEqual(plan.integradas, 20)

    def test_el_voraz_tambien_respeta_el_prefijo(self):
        ramas = [Rama(f"r{i:02d}", Masa(20, 0, 0)) for i in range(20)]
        plan = planificar(ramas, 25.0, maximo_exacto=4)
        self.assertFalse(plan.exacto)
        self.assertEqual(plan.integradas, 1)
        self.assertTrue(all(h > 0 for h in plan.trayectoria))


class TestGrafoDeConflicto(unittest.TestCase):
    """Un choque simbólico no lo arregla el orden: el plan elige un independiente."""

    def _dos_que_chocan(self):
        return [Rama("4f05d2c", Masa(0, 100, 0)), Rama("dedf611", Masa(0, 100, 0))]

    def test_sin_restriccion_integra_las_dos(self):
        plan = planificar(self._dos_que_chocan(), 100.0)
        self.assertEqual(plan.integradas, 2)

    def test_con_la_pareja_marcada_solo_entra_una(self):
        plan = planificar(self._dos_que_chocan(), 100.0, intocables={0: 0b10, 1: 0b01})
        self.assertEqual(plan.integradas, 1)
        self.assertFalse(plan.completo)
        self.assertEqual(len(plan.excluidas), 1)
        self.assertNotIn(plan.excluidas[0], plan.orden)

    def test_el_voraz_tambien_respeta_el_grafo(self):
        ramas = [Rama(f"r{i:02d}", Masa(0, 100, 0)) for i in range(20)]
        plan = planificar(ramas, 100.0, maximo_exacto=4, intocables={0: 0b10, 1: 0b01})
        self.assertFalse(plan.exacto)
        self.assertEqual(plan.integradas, 19)

    def test_un_conflicto_no_impide_integrar_el_resto(self):
        ramas = [
            Rama("a", Masa(0, 90, 0)),
            Rama("b", Masa(0, 90, 0)),
            Rama("c", Masa(0, 90, 0)),
        ]
        plan = planificar(ramas, 50.0, intocables={0: 0b10, 1: 0b01})
        self.assertEqual(sorted(plan.orden), ["a", "c"])
        self.assertEqual(plan.excluidas, ("b",))


if __name__ == "__main__":
    unittest.main()


class TestPesosDeclarados(unittest.TestCase):
    """La función objetivo se declara: sin pesos, cuántas caben; con pesos, cuáles."""

    H0 = 100.0

    def _cinco(self):
        return [
            Rama("liquidez", Masa(0, 70, 0)),
            Rama("estrategica", Masa(190, 0, 0)),
            Rama("barata1", Masa(20, 0, 0)),
            Rama("barata2", Masa(20, 0, 0)),
        ]

    def test_sin_pesos_gana_el_conteo(self):
        plan = planificar(self._cinco(), self.H0)
        self.assertEqual(plan.orden, ("liquidez", "barata1", "barata2"))
        self.assertAlmostEqual(plan.holgura_final, 159.386, places=3)

    def test_un_peso_mete_la_estrategica_a_costa_de_volumen(self):
        plan = planificar(self._cinco(), self.H0, pesos={"estrategica": 10.0})
        self.assertEqual(plan.orden, ("liquidez", "estrategica"))
        self.assertEqual(plan.integradas, 2)
        self.assertAlmostEqual(plan.holgura_final, 9.386, places=3)

    def test_pesos_uniformes_reproducen_el_plan_sin_pesos(self):
        uniforme = planificar(self._cinco(), self.H0, pesos={r.clave: 1.0 for r in self._cinco()})
        self.assertEqual(uniforme, planificar(self._cinco(), self.H0))

    def test_un_peso_cero_excluye_sin_romper_la_solvencia(self):
        plan = planificar(self._cinco(), self.H0, pesos={"barata1": 0.0, "barata2": 0.0})
        self.assertNotIn("barata1", plan.orden)
        self.assertTrue(all(h > 0 for h in plan.trayectoria), plan.trayectoria)
