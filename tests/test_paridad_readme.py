"""La portada como oráculo: `README.md` se mide contra el árbol, no se copia.

Tres citas de la portada envejecieron ya: nueve `@v0.8.0` cuando el release
era `v0.9.0`, «138 pruebas» cuando la suite tenía 147, y «dos puertas por
encima del umbral» cuando sólo una lo estaba. Ninguna rompió un test, porque
nada comparaba la portada con el código. Este banco cierra esa clase: deriva
la verdad del árbol —versión, casos que el descubridor encuentra, universo
versionado— y exige que la portada la cite exactamente.

Límite declarado: mide **citas activas**, lo que un lector obedece al
instalar (`@vX.Y.Z`, `rev: vX.Y.Z`, la URL del release). La prosa histórica
fechada, como `**Corrección v0.8.0 —**`, no es una instrucción y no se toca.
El universo se lee de `git ls-files` —el sujeto versionado, con el mismo
`.gitignore` que ve CI—, no del disco: así un `build/` local no lo mueve.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

from merge_lattice_governor import __version__

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LEEME = RAIZ / "README.md"

ACTIVAS = (
    re.compile(r"@v(?P<v>\d+\.\d+\.\d+)\b"),
    re.compile(r"rev:\s*v(?P<v>\d+\.\d+\.\d+)\b"),
    re.compile(r"releases/download/v(?P<v>\d+\.\d+\.\d+)/"),
)
CASOS = re.compile(r"(?P<n>\d+)\s+pruebas\b")
PRODUCTO = re.compile(r"(?P<n>\d+)\s+archivos? de producto")
PRUEBAS = re.compile(r"(?P<n>\d+)\s+de pruebas")
WHEEL = "merge_lattice_governor-{v}-py3-none-any.whl"
PARTICION = ("tests/",)


def casos_de_prueba() -> int:
    """Cuenta los casos que el propio descubridor de la suite encuentra."""
    suite = unittest.defaultTestLoader.discover(
        str(RAIZ / "tests"), top_level_dir=str(RAIZ)
    )
    return suite.countTestCases()


def universo_versionado() -> tuple[int, int] | None:
    """(producto, pruebas) sobre los `.py` versionados; ``None`` si no hay git."""
    r = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        capture_output=True, cwd=str(RAIZ),
    )
    if r.returncode != 0:
        return None
    rutas = [p for p in r.stdout.decode().split("\0") if p]
    pruebas = sum(1 for p in rutas if p.startswith(PARTICION))
    return len(rutas) - pruebas, pruebas


def _linea(texto: str, pos: int) -> int:
    return texto[:pos].count("\n") + 1


def defectos(
    texto: str,
    version: str,
    pruebas: int,
    universo: tuple[int, int] | None = None,
) -> list[str]:
    """Devuelve las citas de la portada que no cuadran con el árbol."""
    fallos: list[str] = []

    for patron in ACTIVAS:
        for m in patron.finditer(texto):
            if m.group("v") != version:
                fallos.append(
                    f"README:{_linea(texto, m.start())} cita v{m.group('v')} "
                    f"y el código es {version}"
                )

    citas = [(int(m.group("n")), _linea(texto, m.start())) for m in CASOS.finditer(texto)]
    if len(citas) != 1:
        fallos.append(
            f"README declara {len(citas)} conteos de pruebas en las líneas "
            f"{[l for _, l in citas]}; se exige exactamente una cita inequívoca"
        )
    for n, linea in citas:
        if n != pruebas:
            fallos.append(f"README:{linea} declara {n} pruebas y el descubridor cuenta {pruebas}")

    if WHEEL.format(v=version) not in texto:
        fallos.append(f"README no cita el asset {WHEEL.format(v=version)}")

    if universo is not None:
        producto_n, pruebas_n = universo
        for patron, real, nombre in (
            (PRODUCTO, producto_n, "producto"),
            (PRUEBAS, pruebas_n, "pruebas"),
        ):
            hallados = [(int(m.group("n")), _linea(texto, m.start())) for m in patron.finditer(texto)]
            if len(hallados) != 1:
                fallos.append(f"README declara {len(hallados)} cifras de {nombre} versionado")
            for n, linea in hallados:
                if n != real:
                    fallos.append(
                        f"README:{linea} declara {n} archivos de {nombre} y git ls-files da {real}"
                    )

    return fallos


class Paridad(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = LEEME.read_text(encoding="utf-8")
        self.pruebas = casos_de_prueba()
        self.universo = universo_versionado()

    def _solo(self, marca: str) -> None:
        fallos = [f for f in defectos(self.texto, __version__, self.pruebas, self.universo) if marca in f]
        self.assertEqual([], fallos)

    def test_version_activa_coincide_con_el_codigo(self) -> None:
        self._solo("cita v")

    def test_conteo_de_pruebas_citado(self) -> None:
        self._solo("pruebas y el descubridor")

    def test_nombre_del_wheel_citado(self) -> None:
        self._solo("asset")

    def test_universo_versionado_citado(self) -> None:
        if self.universo is None:
            self.skipTest("sin git: el universo versionado no es medible aquí")
        self._solo("git ls-files")

    def test_el_oraculo_muerde(self) -> None:
        """Sin esto el banco pasaría por no mirar: cada mutación debe delatarse."""
        mutaciones = {
            "versión": self.texto.replace(f"@v{__version__}", "@v9.9.9", 1),
            "conteo": self.texto.replace(f"{self.pruebas} pruebas", f"{self.pruebas - 1} pruebas", 1),
            "wheel": self.texto.replace(WHEEL.format(v=__version__), "ausente.whl"),
        }
        if self.universo is not None:
            producto, pruebas = self.universo
            mutaciones["universo"] = self.texto.replace(
                f"{producto} archivos de producto", f"{producto + 1} archivos de producto", 1
            )
            mutaciones["pruebas_versionadas"] = self.texto.replace(
                f"{pruebas} de pruebas", f"{pruebas + 1} de pruebas", 1
            )
        for clase, mutado in mutaciones.items():
            with self.subTest(mutacion=clase):
                self.assertNotEqual(mutado, self.texto, f"la mutación «{clase}» no aplicó")
                self.assertNotEqual(
                    [], defectos(mutado, __version__, self.pruebas, self.universo),
                    f"la portada mutada en «{clase}» pasó el oráculo",
                )
