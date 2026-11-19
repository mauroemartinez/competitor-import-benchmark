"""Pruebas sin datos externos: python -m unittest discover -s tests -v"""

from __future__ import annotations

import unittest

import pandas as pd

from competencia import analisis as a
from competencia import formato as f
from competencia.datos import YO, generar


def preparar(registros: pd.DataFrame) -> pd.DataFrame:
    datos = registros.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha_oficializacion"])
    datos["mes"] = datos["fecha"].dt.to_period("M")
    datos["trimestre"] = datos["fecha"].dt.to_period("Q")
    datos["producto"] = datos["descripcion"].map(a.producto_de)
    datos["modelo_limpio"] = datos["modelo"].map(a.modelo_limpio)
    return a.repartir(datos)


class Datos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registros, cls.reales = generar()
        cls.datos = preparar(cls.registros)

    def test_misma_semilla_mismos_datos(self):
        otra, _ = generar()
        pd.testing.assert_frame_equal(self.registros, otra)

    def test_otra_semilla_otros_datos(self):
        otra, _ = generar(semilla=99)
        self.assertFalse(self.registros["fob_usd"].equals(otra["fob_usd"]))

    def test_reconoce_todos_los_productos(self):
        self.assertEqual(self.datos["producto"].nunique(), 6)
        self.assertFalse(self.datos["producto"].str.contains("sin|Otro").any())

    def test_descripciones_distintas_mismo_producto(self):
        for texto in ["TALADRO PERCUTOR 850W 13MM", "TALADRO PERC. 850 W", "TALADRO/PERCUTOR DE 850 W 13 MM"]:
            self.assertEqual(a.producto_de(texto), "Taladro percutor 850 W")
        self.assertEqual(a.producto_de('AMOLADORA 4 1/2" (115MM)'), "Amoladora 115 mm")
        self.assertEqual(a.producto_de("ATORNILL. INALAMBRICO 20 V C/2 BATERIAS"), "Atornillador 20 V")

    def test_modelos_escritos_distinto(self):
        self.assertEqual({a.modelo_limpio(m) for m in ["T-TP850", "T TP850", "TTP-850"]}, {"TTP850"})


class Reparto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registros, cls.reales = generar()
        cls.datos = preparar(cls.registros)

    def test_conserva_el_total_de_cada_item(self):
        for columna in ["fob", "cif"]:
            declarado = self.datos.groupby(["destinacion", "item"])[f"{columna}_usd"].sum()
            repartido = self.datos.groupby(["destinacion", "item"])[f"{columna}_asignado"].sum()
            pd.testing.assert_series_equal(declarado, repartido, check_names=False, atol=0.01)

    def test_no_toca_las_lineas_con_valor_propio(self):
        propias = self.datos[~self.datos["valor_concentrado"]]
        pd.testing.assert_series_equal(propias["fob_usd"], propias["fob_asignado"], check_names=False)

    def test_por_precio_se_equivoca_menos_que_por_cantidad(self):
        error = a.error_del_reparto(self.datos, self.reales)
        self.assertGreater(error["lineas"], 0)
        self.assertLess(error["por_precio"], 0.05)
        self.assertLess(error["por_precio"], error["por_cantidad"] / 5)


class Medidas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registros, _ = generar()
        cls.datos = preparar(registros)

    def test_participaciones_suman_cien(self):
        tabla = a.participacion(self.datos)
        for columna in ["en_fob", "en_unidades"]:
            sumas = tabla.groupby("trimestre")[columna].sum()
            self.assertTrue(((sumas - 1).abs() < 1e-9).all())
        movil = a.participacion_movil(self.datos)
        self.assertTrue(((movil.groupby("fecha")["en_fob"].sum() - 1).abs() < 1e-9).all())

    def test_el_umbral_es_el_rival_mas_barato(self):
        ultimos = a.ultimos_meses(self.datos, 12)
        tabla = a.precios(ultimos)
        for u in a.umbrales(ultimos, YO):
            rivales = tabla[(tabla["producto"] == u.producto) & (tabla["importador"] != YO)]
            self.assertAlmostEqual(u.su_precio, rivales["fob_unitario"].min())
            self.assertEqual(u.mejor_rival, rivales.loc[rivales["fob_unitario"].idxmin(), "importador"])
            if u.diferencia <= 0.0005:
                self.assertEqual(u.ahorro_posible, 0)

    def test_resumen(self):
        r = a.resumen(self.datos, YO)
        self.assertTrue(0 < r.participacion < 1)
        self.assertTrue(1 <= r.puesto <= r.empresas)
        self.assertLessEqual(r.productos_mas_caros, r.productos)


class Formato(unittest.TestCase):
    def test_numeros_argentinos(self):
        self.assertEqual(f.usd(53835.4), "USD 53.835")
        self.assertEqual(f.usd(17.634, 2), "USD 17,63")
        self.assertEqual(f.pct(0.268), "26,8 %")
        self.assertEqual(f.pct(0.091, signo=True), "+9,1 %")
        self.assertEqual(f.pct(-0.0001, signo=True), "0,0 %")


if __name__ == "__main__":
    unittest.main()
