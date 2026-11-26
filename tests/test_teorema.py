"""Teorema del soporte disjunto, atribución al tronco y rutas que decide un driver.

Cada caso es un repositorio sintético: la medida no depende del corpus que la
descubrió. El diferencial ``--sin-optimizar`` está aquí porque el teorema es un
atajo **exacto**, y un atajo sin diferencial es una opinión.
"""

import json
import pathlib
import subprocess
import tempfile
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


class BlobIdempotente(Base):
    """Tercera poda: dos ramas que dejan la misma firma ``(modo, blob)`` en una ruta común."""

    def _rama_con_modo(self, nombre, archivo, contenido, ejecutable=False):
        if ejecutable:
            self.repo._git("config", "core.fileMode", "true")
        self.repo._git("checkout", "-q", "-B", nombre, "main")
        self.repo._escribir(archivo, contenido)
        if ejecutable:
            (pathlib.Path(self.repo.path) / archivo).chmod(0o755)
        self.repo._git("add", "-A")
        self.repo._git("commit", "-qm", nombre)
        self.repo._git("checkout", "-q", "main")

    def test_misma_firma_es_teorema_y_el_merge_lo_confirma(self):
        contenido = "z = 1\n"
        self._rama_con_modo("a", "nuevo.py", contenido)
        self._rama_con_modo("b", "nuevo.py", contenido)

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.TEOREMA)
        self.assertEqual(p.idempotentes, ("nuevo.py",))
        self.assertEqual(p.clase, P.CONMUTA_LIMPIO)

        q = P.pareja(self.repo.path, "a", "b", optimizar=False)
        self.assertEqual(q.decision, P.MEDIDO)
        self.assertEqual(q.clase, P.CONMUTA_LIMPIO, "la poda no puede cambiar el veredicto")
        self.assertEqual(q.textual, (), "el merge real no choca")

    def test_mismo_blob_con_modo_distinto_no_es_teorema(self):
        contenido = "echo hola\n"
        self._rama_con_modo("a", "m.sh", contenido)
        self._rama_con_modo("b", "m.sh", contenido, ejecutable=True)

        fa = R.firma(self.repo.path, "a", "m.sh")
        fb = R.firma(self.repo.path, "b", "m.sh")
        self.assertIsNotNone(fa)
        self.assertEqual(fa[1], fb[1], "los bytes son los mismos: lo que difiere es el modo")
        self.assertNotEqual(fa[0], fb[0])

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.MEDIDO, "mismo blob con otro modo choca: no hay atajo")
        self.assertEqual(p.idempotentes, ())
        self.assertEqual(p.clase, P.CONFLICTO_TEXTUAL)
        self.assertEqual(p.propias, ("m.sh",))

        q = P.pareja(self.repo.path, "a", "b", optimizar=False)
        self.assertEqual(q.clase, p.clase, "la poda no puede cambiar el veredicto")

    def test_borrado_en_las_dos_ramas_es_idempotente(self):
        self.repo._git("checkout", "-q", "main")
        self.repo._escribir("efimero.txt", "x\n")
        self.repo._git("add", "-A")
        self.repo._git("commit", "-qm", "efimero")
        for nombre in ("a", "b"):
            self.repo._git("checkout", "-q", "-B", nombre, "main")
            self.repo._git("rm", "-q", "efimero.txt")
            self.repo._git("commit", "-qm", f"{nombre} borra")
            self.repo._git("checkout", "-q", "main")

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.TEOREMA)
        self.assertEqual(p.idempotentes, ("efimero.txt",))

        q = P.pareja(self.repo.path, "a", "b", optimizar=False)
        self.assertEqual(q.clase, P.CONMUTA_LIMPIO, "la poda no puede cambiar el veredicto")


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


class MatrizEnHilos(Base):
    """``jobs > 1`` no puede cambiar la matriz: mismo orden, mismos veredictos.

    El diferencial es la prueba de que paralelizar no inventó ninguna medida — si
    un hilo comparte el oráculo de ``merge-tree`` a medias, aquí se ve.
    """

    def test_serie_y_hilos_dan_la_misma_matriz(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.repo.rama("b", "otro.py", "x = 1\n")
        self.repo.rama("c", "app.py", APP.replace("v1 = 1", "v1 = 5"))
        self.repo.rama("d", "app.py", APP.replace("v1 = 1", "v1 = 9"))
        refs = ["a", "b", "c", "d"]

        serie = P.matriz(self.repo.path, refs, jobs=1)
        hilos = P.matriz(self.repo.path, refs, jobs=4)
        self.assertEqual(len(serie), 6)
        self.assertEqual(
            [(p.a, p.b, p.base, p.clase, p.textual, p.decision) for p in serie],
            [(p.a, p.b, p.base, p.clase, p.textual, p.decision) for p in hilos],
        )
        self.assertEqual(P.decisiones(hilos), P.decisiones(serie))

    def test_un_solo_par_no_abre_hilos(self):
        self.repo.rama("a", "app.py", APP.replace("v0 = 0", "v0 = 100"))
        self.assertEqual(len(P.matriz(self.repo.path, ["a"], jobs=4)), 0)


class ClonParcial(Base):
    """Un clon `--filter=blob:none` sale RC 128: la causa se nombra, no se adivina.

    Medido el 26-Nov-2026 en `encode/httpx`: `merge-tree` no puede leer un blob
    que el filtro no trajo, y el mensaje genérico mandaba a buscar un git viejo.
    """

    def test_rc_128_por_blob_ausente_nombra_el_clon_parcial(self):
        proc = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="",
            stderr="fatal: unable to read blob object e84a4d7b3dd81c336478f9164d59ec65ca2b0237\n",
        )
        causa = R._causa_merge_tree(proc, "a", "b")
        self.assertIn("RC 128", causa)
        self.assertIn("clon parcial", causa)
        self.assertIn("--filter", causa, "la causa sin remedio deja al operador parado")

    def test_rc_128_en_clon_superficial_no_se_disfraza_de_clon_parcial(self):
        """Medido el 27-Nov-2026: un clon ``--depth 1`` de la propia v0.5.0 salió
        «clon parcial · clonar sin --filter», y el remedio era otro."""
        proc = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="",
            stderr="error: Could not read fffb64633adf9d8ceb45fbbf9caee1df5bffda70\n",
        )
        causa = R._causa_merge_tree(proc, "a", "b")
        self.assertIn("clon superficial", causa)
        self.assertIn("--unshallow", causa, "la causa sin remedio deja al operador parado")
        self.assertNotIn("clon parcial", causa)
        self.assertNotIn("no puede distinguir", causa, "la cola genérica sobra cuando la causa se nombra")

    def test_la_superficialidad_se_mide_y_no_se_supone(self):
        """Un directorio sin git, y un repo sin recortar, no son «superficiales»."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(R._es_superficial(tmp))
            self.assertEqual(subprocess.run(["git", "-C", tmp, "init", "-q"], capture_output=True).returncode, 0)
            self.assertFalse(R._es_superficial(tmp), "git init: historia completa por construcción")

    def test_rc_128_por_otra_causa_no_se_disfraza_de_clon_parcial(self):
        proc = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="", stderr="fatal: not a git repository\n",
        )
        causa = R._causa_merge_tree(proc, "a", "b")
        self.assertNotIn("clon parcial", causa)
        self.assertIn("not a git repository", causa)


class ColisionArchivoDirectorio(Base):
    """`d` frente a `d/x`: soporte disjunto que **sí** choca (medido 28-Nov-2026)."""

    def test_soporte_disjunto_por_prefijo_no_es_teorema(self):
        self.repo.rama("a", "dw", "soy archivo\n")
        self.repo.rama("b", "dw/inner.txt", "soy hijo\n")

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.decision, P.MEDIDO, "el atajo por soporte no puede decidir este par")
        self.assertEqual(p.clase, P.CONFLICTO_TEXTUAL)
        self.assertTrue(p.prefijo, "el veredicto debe decir por qué no aplicó el atajo")

        q = P.pareja(self.repo.path, "a", "b", optimizar=False)
        self.assertEqual(q.clase, p.clase, "el atajo no puede cambiar el veredicto")

    def test_prefijo_que_no_choca_se_mide_igual(self):
        """Un directorio nuevo a cada lado no es choque: `dw/a` frente a `dw/b` conmuta."""
        self.repo.rama("a", "dw/a.txt", "a\n")
        self.repo.rama("b", "dw/b.txt", "b\n")

        p = P.pareja(self.repo.path, "a", "b")
        self.assertEqual(p.prefijo, (), "compartir directorio no es pelear por el nombre")
        self.assertEqual(p.decision, P.TEOREMA)
        self.assertEqual(p.clase, P.CONMUTA_LIMPIO)


if __name__ == "__main__":
    unittest.main()
