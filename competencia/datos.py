"""Genera los registros de importación sintéticos del ejemplo.

Cinco importadores inventados (tu empresa y cuatro rivales) traen la misma
familia de productos, herramientas eléctricas de proveedores chinos, durante 24
meses. Los registros tienen la forma de los de la aduana argentina: una
destinación por embarque, ítems por posición arancelaria, subítems por modelo,
FOB, flete, seguro y CIF, y descripciones escritas cada una a su manera.

Como en los registros reales, en algunos ítems con varios modelos el valor
entero figura en la primera línea y las demás quedan en cero. El análisis tiene
que repartirlo. Acá el reparto se puede auditar, porque el generador guarda
aparte el valor verdadero de cada línea (data/valores_reales.csv).

Todo es inventado: empresas, marcas, modelos y precios. Con la misma semilla,
el resultado es siempre el mismo.

uso: python -m competencia.datos [--semilla 2]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "data"
REGISTROS = CARPETA / "registros_importacion.csv"
VALORES_REALES = CARPETA / "valores_reales.csv"

YO = "Tu empresa"
INICIO, FIN = "2024-10", "2026-09"

# producto: (posición, código corto, FOB base en USD por unidad, unidades base por línea)
PRODUCTOS = {
    "Taladro percutor 650 W": ("8467.21.00", "TP650", 13.80, 1200),
    "Taladro percutor 850 W": ("8467.21.00", "TP850", 18.90, 900),
    "Amoladora 115 mm": ("8467.29.00", "AM115", 10.60, 1500),
    "Amoladora 180 mm": ("8467.29.00", "AM180", 23.50, 500),
    "Atornillador 12 V": ("8467.21.00", "AT12", 15.40, 900),
    "Atornillador 20 V": ("8467.21.00", "AT20", 36.80, 400),
}
NOMBRES = list(PRODUCTOS)

# Cómo escribe cada uno la descripción: el mismo producto llega de muchas formas.
DESCRIPCIONES = {
    "Taladro percutor 650 W": ["TALADRO PERCUTOR 650W 13MM", "TALADRO PERC. 650 W", "TALADRO/PERCUTOR DE 650 W 13 MM"],
    "Taladro percutor 850 W": ["TALADRO PERCUTOR 850W 13MM", "TALADRO PERC. 850 W", "TALADRO/PERCUTOR DE 850 W 13 MM"],
    "Amoladora 115 mm": ["AMOLADORA ANGULAR 115MM 750W", "AMOLADORA ANG. 115 MM", 'AMOLADORA 4 1/2" (115MM)'],
    "Amoladora 180 mm": ["AMOLADORA ANGULAR 180MM 2000W", "AMOLADORA ANG. 180 MM", 'AMOLADORA 7" (180MM) 2000 W'],
    "Atornillador 12 V": ["ATORNILLADOR INALAMBRICO 12V", "ATORNILL. INALAMBRICO 12 V", "ATORNILLADOR A BATERIA 12V"],
    "Atornillador 20 V": ["ATORNILLADOR INALAMBRICO 20V 2 BAT", "ATORNILL. INALAMBRICO 20 V C/2 BATERIAS", "ATORNILLADOR A BATERIA 20V"],
}

# Cada importador: su marca, cuántos embarques hace por mes, qué tamaño de lote,
# cómo crece o cae su volumen en los 24 meses, a qué precio compra cada producto
# (relativo al base, en el orden de PRODUCTOS) y qué mezcla trae.
IMPORTADORES = {
    YO: dict(
        marca="MARCA T", prefijo="T", aduana=("001", "BUENOS AIRES"), via="MARITIMA",
        embarques=4.0, lote=0.33, crecimiento=0.45, incoterm=["FOB"],
        precio=[1.03, 1.08, 1.05, 0.99, 1.04, 0.97],
        mezcla=[0.15, 0.25, 0.15, 0.10, 0.15, 0.20], flete=0.080,
    ),
    "Rival Norte": dict(
        marca="MARCA K", prefijo="K", aduana=("001", "BUENOS AIRES"), via="MARITIMA",
        embarques=6.0, lote=0.2, crecimiento=0.05, incoterm=["FOB", "EXW"],
        precio=[1.07, 1.10, 1.08, 1.06, 1.06, 1.05],
        mezcla=[0.25, 0.15, 0.30, 0.10, 0.15, 0.05], flete=0.095,
    ),
    "Rival Sur": dict(
        marca="MARCA L", prefijo="L", aduana=("001", "BUENOS AIRES"), via="MARITIMA",
        embarques=2.0, lote=0.95, crecimiento=0.0, incoterm=["FOB"],
        precio=[0.97, 0.99, 0.98, 1.00, 0.97, 1.01],
        mezcla=[0.15, 0.20, 0.20, 0.15, 0.15, 0.15], flete=0.060,
    ),
    "Rival Litoral": dict(
        marca="MARCA M", prefijo="M", aduana=("052", "ROSARIO"), via="MARITIMA",
        embarques=3.0, lote=0.4, crecimiento=-0.35, incoterm=["CFR", "FOB"],
        precio=[1.01, 1.03, 1.00, 1.03, 1.02, 0.99],
        mezcla=[0.20, 0.20, 0.15, 0.20, 0.10, 0.15], flete=0.075,
    ),
    "Rival Cuyo": dict(
        marca="MARCA N", prefijo="N", aduana=("038", "MENDOZA"), via="TERRESTRE",
        embarques=1.6, lote=0.35, crecimiento=0.10, incoterm=["FOB"],
        precio=[1.00, 1.02, 0.97, 1.04, 0.99, 1.03],
        mezcla=[0.10, 0.15, 0.25, 0.25, 0.15, 0.10], flete=0.110,
    ),
}

SEMILLA = 2
CAIDA_ANUAL = 0.04  # los precios de origen bajan un 4 % por año
CONCENTRADOS = 0.35  # parte de los ítems con varios modelos que declaran todo en una línea


def generar(semilla: int = SEMILLA) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (registros como los publica la aduana, valores reales por línea)."""
    rng = np.random.default_rng(semilla)
    meses = pd.period_range(INICIO, FIN, freq="M")
    filas: list[dict] = []
    numeradores: dict[tuple[str, str], int] = {}

    for empresa, perfil in IMPORTADORES.items():
        for i, mes in enumerate(meses):
            t = i / (len(meses) - 1)
            # Compran con regularidad: la parte entera de la tasa siempre, la fracción a veces.
            tasa = perfil["embarques"] * (1 + perfil["crecimiento"] * t)
            cantidad_embarques = int(tasa) + int(rng.random() < tasa - int(tasa))
            for _ in range(cantidad_embarques):
                dia = int(rng.integers(1, mes.days_in_month + 1))
                fecha = pd.Timestamp(year=mes.year, month=mes.month, day=dia)
                codigo, aduana = perfil["aduana"]
                clave = (str(fecha.year)[2:], codigo)
                numeradores[clave] = numeradores.get(clave, int(rng.integers(1000, 9000))) + int(rng.integers(1, 40))
                letra = "ABCDEFGHJKLMNPRSTUVWXYZ"[int(rng.integers(0, 23))]
                destinacion = f"{clave[0]}{codigo}IC04{numeradores[clave]:06d}{letra}"
                incoterm = str(rng.choice(perfil["incoterm"]))
                origen = "VIETNAM" if rng.random() < 0.06 else "CHINA"

                cuantos = int(rng.integers(2, 5))
                elegidos = rng.choice(len(NOMBRES), size=cuantos, replace=False, p=perfil["mezcla"])
                lineas = []
                for j in sorted(elegidos):
                    producto = NOMBRES[j]
                    posicion, corto, base, unidades = PRODUCTOS[producto]
                    cantidad = max(20, int(round(rng.lognormal(np.log(unidades * perfil["lote"]), 0.30) / 10)) * 10)
                    deriva = 1 - CAIDA_ANUAL * (fecha - pd.Timestamp(INICIO)).days / 365
                    unitario = round(base * perfil["precio"][j] * deriva * (1 + rng.normal(0, 0.025)), 2)
                    fob = round(unitario * cantidad, 2)
                    tasa_flete = perfil["flete"] * (1 + rng.normal(0, 0.12))
                    flete = round(fob * tasa_flete, 2)
                    seguro = round((fob + flete) * 0.005, 2)
                    modelo = escribir_modelo(perfil["prefijo"], corto, rng)
                    descripcion = f"{rng.choice(DESCRIPCIONES[producto])} MARCA: {perfil['marca']} MOD: {modelo}"
                    lineas.append(dict(
                        fecha_oficializacion=fecha.date().isoformat(), destinacion=destinacion,
                        aduana=aduana, importador=empresa, pais_origen=origen, via=perfil["via"],
                        incoterm=incoterm, posicion=posicion, descripcion=descripcion,
                        marca=perfil["marca"], modelo=modelo, unidad="UNIDAD", cantidad=cantidad,
                        fob_usd=fob, flete_usd=flete, seguro_usd=seguro,
                        cif_usd=round(fob + flete + seguro, 2),
                    ))

                # Un ítem por posición arancelaria y un subítem por modelo.
                for item, posicion in enumerate(sorted({linea["posicion"] for linea in lineas}), start=1):
                    del_item = [linea for linea in lineas if linea["posicion"] == posicion]
                    concentrar = len(del_item) > 1 and rng.random() < CONCENTRADOS
                    totales = {c: round(sum(linea[c] for linea in del_item), 2) for c in ("fob_usd", "flete_usd", "seguro_usd", "cif_usd")}
                    for subitem, linea in enumerate(del_item, start=1):
                        linea["item"], linea["subitem"] = item, subitem
                        for c in ("fob_usd", "flete_usd", "seguro_usd", "cif_usd"):
                            linea[f"{c.removesuffix('_usd')}_real_usd"] = linea[c]
                            if concentrar:
                                linea[c] = totales[c] if subitem == 1 else 0.0
                        filas.append(linea)

    datos = pd.DataFrame(filas).sort_values(["fecha_oficializacion", "destinacion", "item", "subitem"])
    datos = datos.reset_index(drop=True)
    reales = ["fob_real_usd", "flete_real_usd", "seguro_real_usd", "cif_real_usd"]
    columnas = [
        "fecha_oficializacion", "destinacion", "item", "subitem", "aduana", "importador",
        "pais_origen", "via", "incoterm", "posicion", "descripcion", "marca", "modelo",
        "unidad", "cantidad", "fob_usd", "flete_usd", "seguro_usd", "cif_usd",
    ]
    return datos[columnas], datos[["destinacion", "item", "subitem", *reales]]


def escribir_modelo(prefijo: str, corto: str, rng: np.random.Generator) -> str:
    """El mismo modelo llega escrito de varias formas: T-TP850, T TP850, TTP-850."""
    forma = rng.random()
    if forma < 0.7:
        return f"{prefijo}-{corto}"
    if forma < 0.85:
        return f"{prefijo} {corto}"
    letras = corto.rstrip("0123456789")
    return f"{prefijo}{letras}-{corto[len(letras):]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    args = parser.parse_args()
    registros, reales = generar(args.semilla)
    CARPETA.mkdir(exist_ok=True)
    registros.to_csv(REGISTROS, index=False)
    reales.to_csv(VALORES_REALES, index=False)
    concentradas = int((registros["fob_usd"] == 0).sum())
    print(
        f"{len(registros)} líneas en {registros['destinacion'].nunique()} destinaciones, "
        f"{concentradas} con el valor concentrado en otra línea -> {REGISTROS.relative_to(RAIZ)}"
    )


if __name__ == "__main__":
    main()
