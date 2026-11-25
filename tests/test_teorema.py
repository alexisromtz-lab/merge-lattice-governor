"""Teorema del soporte disjunto, atribución al tronco y rutas que decide un driver.

Cada caso es un repositorio sintético: la medida no depende del corpus que la
descubrió. El diferencial ``--sin-optimizar`` está aquí porque el teorema es un
atajo **exacto**, y un atajo sin diferencial es una opinión.
"""

import json
import unittest

from merge_lattice_governor import parejas as P
from merge_lattice_governor import repo as R

from .test_extremo_a_extremo import APP, RepoDePrueba, _corre


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = RepoDePrueba()

    def tearDown(self):
        self.repo.cerrar()

    def commit_tronco(self, archivo, contenido, mensaje="tronco avanza"):
        self.repo._git("checkout", "-q", "main")
        self.repo._escribir(archivo, contenido)
        self.repo._git("add", "-A")
        self.repo._git("commit", "-qm", mensaje)


class SoporteDisjunto(Base):
    def test_sin_rutas_comunes_es_teorema_y_el_merge_lo_confirma(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "otro.py", "x = 1\n")

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.TEOREMA)
        self.assertEqual(p.textual, ())
        self.assertEqual(p.clase, P.CONMUTA_LIMPIO)

        q = P.pareja(self.repo.path, "a", "b", optimizar=False)
        self.assertEqual(q.decision, P.MEDIDO)
        self.assertEqual(q.clase, P.CONMUTA_LIMPIO, "el teorema no puede cambiar el veredicto")

    def test_soporte_comun_no_es_soporte_que_choca(self):
        """Solapar archivo no es chocar: dos regiones distintas del mismo archivo conmutan."""
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v30 = 30", "v30 = 330"))

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.MEDIDO, "con soporte común hay que mergear")
        self.assertEqual(p.clase, P.CONMUTA_LIMPIO)

    def test_misma_linea_es_conflicto_propio(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v0 = 0", "v0 = -100"))

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.clase, P.CONFLICTO_TEXTUAL)
        self.assertEqual(p.propias, ("app.py",))
        self.assertEqual(p.driver, ())


class DriverDecide(Base):
    def setUp(self):
        super().setUp()
        self.repo._escribir(".gitattributes", "app.py merge=nuestro\n")
        self.repo._git("add", "-A")
        self.repo._git("commit", "-qm", "atributos")
        self.repo._git("config", "merge.nuestro.driver", "false")
        self.repo._git("config", "merge.nuestro.name", "driver que para")

    def test_merge_generico_limpio_no_es_veredicto_cuando_hay_driver(self):
        """El caso que se leía limpio: rutas distintas, merge genérico sin marcas.

        El driver corre igual en el merge real y este instrumento no lo ejecuta:
        el par no es limpio ni rojo, es NO_MEDIDO con su driver nombrado.
        """
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v30 = 30", "v30 = 330"))

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.textual, (), "el merge genérico no ve conflicto aquí")
        self.assertEqual(p.driver, ("app.py merge=nuestro",))
        self.assertEqual(p.clase, P.NO_MEDIDO)
        self.assertIn("merge=nuestro", p.describe())

        sin_driver = P.pareja(self.repo.path, "a", "b", driver=False)
        self.assertEqual(sin_driver.clase, P.CONMUTA_LIMPIO, "--ignorar-driver es el merge puro")

    def test_conflicto_generico_en_ruta_de_driver_tampoco_es_mio(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v0 = 0", "v0 = -100"))

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.textual, ("app.py",))
        self.assertEqual(p.propias, (), "la ruta la decide el driver, no el merge genérico")
        self.assertEqual(p.clase, P.NO_MEDIDO)


class Atribucion(Base):
    def _fric(self, *refs):
        return P.fricciones(self.repo.path, "main", list(refs))

    def test_choque_que_ya_tenia_con_el_tronco_se_atribuye_al_tronco(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v0 = 0", "v0 = -100"))
        self.commit_tronco("app.py", APP.replace("v0 = 0", "v0 = 7"))

        fric = self._fric("a", "b")
        self.assertEqual(fric["a"], ("app.py",), "la rama ya choca con el tronco en esa ruta")
        self.assertEqual(fric["b"], ("app.py",))

        (p,) = P.anotar([P.pareja(self.repo.path, "a", "b")], fric)
        self.assertEqual(p.atribucion, P.ATRIBUCION_TRONCO)
        self.assertIn("rebasa primero", p.describe())

    def test_choque_en_ruta_que_el_tronco_no_toca_es_del_par(self):
        self.commit_tronco("zeta.py", "z = 0\n", "base con zeta")
        self.repo.rama("c", "zeta.py", "z = 1\n")
        self.repo.rama("d", "zeta.py", "z = 2\n")

        fric = self._fric("c", "d")
        self.assertEqual(fric["c"], (), "el tronco no ha tocado zeta: no hay fricción")

        (p,) = P.anotar([P.pareja(self.repo.path, "c", "d")], fric)
        self.assertEqual(p.clase, P.CONFLICTO_TEXTUAL)
        self.assertEqual(p.atribucion, P.ATRIBUCION_PAR)

    def test_rama_al_dia_no_gasta_merge(self):
        self.repo.rama("e", "otro.py", "y = 1\n")
        self.commit_tronco("tercero.py", "w = 1\n")
        self.assertEqual(self._fric("e"), {"e": ()})


class PredicadoExacto(Base):
    def test_referencia_ausente_no_es_par_limpio(self):
        """RC 1 con stdout vacío es un merge que no corrió: leerse limpio es el falso verde."""
        with self.assertRaises(R.ErrorGit):
            R.rutas_en_conflicto(self.repo.path, "no-existe", "main")

    def test_no_escribe_en_el_odb_del_sujeto(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "app.py", APP.replace("v0 = 0", "v0 = -100"))
        antes = self.repo._git("count-objects", "-v")
        R.rutas_en_conflicto(self.repo.path, "a", "b")
        self.assertEqual(self.repo._git("count-objects", "-v"), antes)


class DiferencialCLI(Base):
    def test_las_dos_vias_dan_el_mismo_veredicto(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "otro.py", "x = 1\n")
        self.repo.rama("c", "app.py", APP.replace("v1 = 1", "v1 = 5"))

        clases = []
        for extra in ([], ["--sin-optimizar"]):
            rc, salida = _corre(self.repo.path, "--sin-plan", "--sin-friccion",
                                "--ref", "a", "--ref", "b", "--ref", "c", "--json", *extra)
            self.assertEqual(rc, 0, salida)
            datos = json.loads(salida)
            clases.append([(p["clase"], p["textual"]) for p in datos["parejas"]])
        self.assertEqual(clases[0], clases[1])
        self.assertEqual(json.loads(salida)["decisiones"], {P.TEOREMA: 0, P.MEDIDO: 3})


if __name__ == "__main__":
    unittest.main()
