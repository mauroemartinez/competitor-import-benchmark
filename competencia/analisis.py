"""Del registro aduanero a la lectura de compras.

Tres pasos:
1. Normalizar: cada empresa describe el mismo producto a su manera. Se lo
   reconoce por la descripción (tipo y potencia o medida), no por el modelo,
   que cambia de marca a marca.
2. Repartir: cuando un ítem trae varios modelos y el valor entero figura en
   una sola línea, se lo reparte por cantidad por el precio de referencia de
   cada producto. Sin ese paso, el precio por modelo sale mal.
3. Medir: a qué precio compra cada uno, cuánto pesa cada uno en el mercado,
   cada cuánto compra y en qué lotes, y qué significa para tu próxima cotización.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .datos import REGISTROS, VALORES_REALES, YO

VALORES = ["fob_usd", "flete_usd", "seguro_usd", "cif_usd"]


# 1. Normalizar ---------------------------------------------------------------

def producto_de(descripcion: str) -> str:
    """Reconoce el producto por la descripción, la escriba como la escriba."""
    texto = descripcion.upper()
    if "TALADRO" in texto:
        potencia = re.search(r"(\d{3,4})\s*W", texto)
        return f"Taladro percutor {potencia.group(1)} W" if potencia else "Taladro sin potencia"
    if "AMOLADORA" in texto:
        medida = re.search(r"(\d{3})\s*MM", texto)
        return f"Amoladora {medida.group(1)} mm" if medida else "Amoladora sin medida"
    if "ATORNILL" in texto:
        tension = re.search(r"(\d{2})\s*V\b", texto)
        return f"Atornillador {tension.group(1)} V" if tension else "Atornillador sin tensión"
    return "Otro"


def modelo_limpio(modelo: str) -> str:
    """T-TP850, T TP850 y TTP-850 son el mismo modelo: queda TTP850."""
    return re.sub(r"[^A-Z0-9]", "", str(modelo).upper())


def cargar(ruta=REGISTROS) -> pd.DataFrame:
    datos = pd.read_csv(ruta, dtype={"posicion": str, "destinacion": str})
    datos["fecha"] = pd.to_datetime(datos["fecha_oficializacion"])
    datos["mes"] = datos["fecha"].dt.to_period("M")
    datos["trimestre"] = datos["fecha"].dt.to_period("Q")
    datos["producto"] = datos["descripcion"].map(producto_de)
    datos["modelo_limpio"] = datos["modelo"].map(modelo_limpio)
    return repartir(datos)


# 2. Repartir -----------------------------------------------------------------

def repartir(datos: pd.DataFrame, por_precio: bool = True) -> pd.DataFrame:
    """Agrega fob_asignado, flete_asignado, seguro_asignado y cif_asignado.

    En un ítem con valor concentrado (varias líneas, alguna en cero) el total
    del ítem se reparte entre sus líneas. Con por_precio, cada línea pesa su
    cantidad por el precio de referencia de su producto: el que paga ese mismo
    importador en las líneas que sí traen su valor, o si no hay, el del mercado.
    Sin por_precio, pesa solo la cantidad (el reparto ingenuo).
    """
    datos = datos.copy()
    claves = ["destinacion", "item"]
    grupo = datos.groupby(claves)
    lineas = grupo["fob_usd"].transform("size")
    con_valor = grupo["fob_usd"].transform(lambda s: int((s > 0).sum()))
    datos["valor_concentrado"] = (lineas > 1) & (con_valor < lineas)

    if por_precio:
        propias = datos[~datos["valor_concentrado"]]
        suma = propias.groupby(["importador", "producto"])[["fob_usd", "cantidad"]].sum()
        ref_empresa = (suma["fob_usd"] / suma["cantidad"]).rename("ref_empresa")
        suma_mercado = propias.groupby("producto")[["fob_usd", "cantidad"]].sum()
        ref_mercado = (suma_mercado["fob_usd"] / suma_mercado["cantidad"]).rename("ref_mercado")
        referencia = (
            datos[["importador", "producto"]]
            .join(ref_empresa, on=["importador", "producto"])
            .join(ref_mercado, on="producto")
        )
        precio = referencia["ref_empresa"].fillna(referencia["ref_mercado"]).fillna(1.0)
        peso = datos["cantidad"] * precio
    else:
        peso = datos["cantidad"].astype(float)

    peso_item = peso.groupby([datos[c] for c in claves]).transform("sum")
    for columna in VALORES:
        total_item = datos.groupby(claves)[columna].transform("sum")
        asignado = np.where(datos["valor_concentrado"], total_item * peso / peso_item, datos[columna])
        datos[columna.replace("_usd", "_asignado")] = asignado
    return datos


def error_del_reparto(datos: pd.DataFrame, reales: pd.DataFrame | None = None) -> dict[str, float]:
    """Cuánto se equivoca el reparto, línea por línea, contra el valor verdadero.

    Solo se puede medir con datos sintéticos, porque el generador guarda el
    valor real de cada línea. Devuelve el error medio en las líneas concentradas
    con el reparto por precio de referencia y con el reparto solo por cantidad.
    """
    if reales is None:
        reales = pd.read_csv(VALORES_REALES, dtype={"destinacion": str})
    claves = ["destinacion", "item", "subitem"]
    por_precio = repartir(datos, por_precio=True).merge(reales, on=claves)
    por_cantidad = repartir(datos, por_precio=False).merge(reales, on=claves)

    def error(tabla: pd.DataFrame) -> float:
        filas = tabla[tabla["valor_concentrado"]]
        return float((filas["fob_asignado"] / filas["fob_real_usd"] - 1).abs().mean())

    return {
        "lineas": int(por_precio["valor_concentrado"].sum()),
        "por_precio": error(por_precio),
        "por_cantidad": error(por_cantidad),
    }


# 3. Medir --------------------------------------------------------------------

def ultimos_meses(datos: pd.DataFrame, meses: int = 12, corrimiento: int = 0) -> pd.DataFrame:
    """Las filas de los últimos `meses` meses, corridos `corrimiento` meses hacia atrás."""
    fin = datos["mes"].max() - corrimiento
    inicio = fin - (meses - 1)
    return datos[(datos["mes"] >= inicio) & (datos["mes"] <= fin)]


def precios(datos: pd.DataFrame) -> pd.DataFrame:
    """Precio unitario FOB y CIF de cada importador en cada producto."""
    suma = datos.groupby(["producto", "importador"])[["fob_asignado", "cif_asignado", "cantidad"]].sum()
    tabla = pd.DataFrame({
        "fob_unitario": suma["fob_asignado"] / suma["cantidad"],
        "cif_unitario": suma["cif_asignado"] / suma["cantidad"],
        "unidades": suma["cantidad"],
        "fob": suma["fob_asignado"],
    })
    return tabla.reset_index()


def participacion(datos: pd.DataFrame, por: str = "trimestre") -> pd.DataFrame:
    """Participación de cada importador en FOB y en unidades, por período."""
    suma = datos.groupby([por, "importador"])[["fob_asignado", "cantidad"]].sum()
    total = suma.groupby(level=0).transform("sum")
    tabla = (suma / total).rename(columns={"fob_asignado": "en_fob", "cantidad": "en_unidades"})
    return tabla.reset_index()


def participacion_movil(datos: pd.DataFrame, meses: int = 6) -> pd.DataFrame:
    """Participación en FOB de cada importador, mes a mes, sobre los últimos `meses` meses.

    Un importador que compra poco y grande hace saltar la participación de un
    trimestre a otro; la ventana móvil deja ver la tendencia.
    """
    fob = datos.groupby(["mes", "importador"])["fob_asignado"].sum().unstack(fill_value=0)
    fob = fob.reindex(pd.period_range(fob.index.min(), fob.index.max(), freq="M"), fill_value=0)
    suma = fob.rolling(meses).sum().dropna()
    tabla = suma.div(suma.sum(axis=1), axis=0)
    tabla.index = tabla.index.to_timestamp()
    tabla.index.name = "fecha"
    return tabla.reset_index().melt(id_vars="fecha", var_name="importador", value_name="en_fob")


def como_compra(datos: pd.DataFrame) -> pd.DataFrame:
    """Cada cuánto compra cada uno, en qué lotes y cuánto paga de flete y seguro."""
    embarques = (
        datos.groupby(["importador", "destinacion"])
        .agg(fecha=("fecha", "min"), unidades=("cantidad", "sum"), fob=("fob_asignado", "sum"), cif=("cif_asignado", "sum"))
        .reset_index()
    )
    meses = datos["mes"].nunique()
    filas = []
    for empresa, suyos in embarques.groupby("importador"):
        fechas = suyos["fecha"].sort_values()
        filas.append({
            "importador": empresa,
            "embarques_por_anio": len(suyos) / meses * 12,
            "unidades_por_embarque": suyos["unidades"].mean(),
            "dias_entre_compras": fechas.diff().dt.days.median(),
            "fob_total": suyos["fob"].sum(),
            "flete_y_seguro": suyos["cif"].sum() / suyos["fob"].sum() - 1,
        })
    return pd.DataFrame(filas)


def mezcla(datos: pd.DataFrame) -> pd.DataFrame:
    """Qué parte de su FOB pone cada importador en cada producto."""
    suma = datos.pivot_table(index="importador", columns="producto", values="fob_asignado", aggfunc="sum", fill_value=0)
    return suma.div(suma.sum(axis=1), axis=0)


@dataclass
class Umbral:
    producto: str
    tu_precio: float
    mejor_rival: str
    su_precio: float
    diferencia: float  # tu precio contra el del mejor rival, en tanto por uno
    tus_unidades: int
    ahorro_posible: float  # USD, si hubieras pagado lo que paga el mejor rival


def umbrales(datos: pd.DataFrame, yo: str = YO) -> list[Umbral]:
    """Para cada producto que comprás, el precio del rival que mejor compra.

    Ese precio es tu umbral: si te cotizan arriba, pagás más que él.
    """
    tabla = precios(datos)
    resultado = []
    for producto, filas in tabla.groupby("producto"):
        mia = filas[filas["importador"] == yo]
        rivales = filas[filas["importador"] != yo]
        if mia.empty or rivales.empty:
            continue
        mejor = rivales.loc[rivales["fob_unitario"].idxmin()]
        tu_precio = float(mia["fob_unitario"].iloc[0])
        su_precio = float(mejor["fob_unitario"])
        unidades = int(mia["unidades"].iloc[0])
        diferencia = tu_precio / su_precio - 1
        resultado.append(Umbral(
            producto=producto,
            tu_precio=tu_precio,
            mejor_rival=str(mejor["importador"]),
            su_precio=su_precio,
            diferencia=diferencia,
            tus_unidades=unidades,
            # Menos de 0,05 % de diferencia es empate: no hay ahorro que contar.
            ahorro_posible=(tu_precio - su_precio) * unidades if diferencia > 0.0005 else 0.0,
        ))
    return sorted(resultado, key=lambda u: -u.diferencia)


def precio_mensual(datos: pd.DataFrame, producto: str) -> pd.DataFrame:
    """Precio FOB unitario de cada importador, mes a mes, en un producto."""
    filas = datos[datos["producto"] == producto]
    suma = filas.groupby(["mes", "importador"])[["fob_asignado", "cantidad"]].sum().reset_index()
    suma["fob_unitario"] = suma["fob_asignado"] / suma["cantidad"]
    suma["fecha"] = suma["mes"].dt.to_timestamp()
    return suma


@dataclass
class Resumen:
    participacion: float
    participacion_anterior: float
    puesto: int
    lider: str
    empresas: int
    productos_mas_caros: int
    productos: int
    ahorro_posible: float


def resumen(datos: pd.DataFrame, yo: str = YO) -> Resumen:
    """Las cuatro cifras de arriba del informe, sobre los últimos 12 meses."""
    actual = ultimos_meses(datos, 12)
    anterior = ultimos_meses(datos, 12, corrimiento=12)
    fob = actual.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False)
    fob_anterior = anterior.groupby("importador")["fob_asignado"].sum()
    lista = umbrales(actual, yo)
    return Resumen(
        participacion=float(fob.get(yo, 0) / fob.sum()),
        participacion_anterior=float(fob_anterior.get(yo, 0) / fob_anterior.sum()) if len(fob_anterior) else float("nan"),
        puesto=int(list(fob.index).index(yo) + 1),
        lider=str(fob.index[0]) if fob.index[0] != yo else str(fob.index[1]),
        empresas=len(fob),
        productos_mas_caros=sum(1 for u in lista if u.diferencia > 0.0005),
        productos=len(lista),
        ahorro_posible=sum(u.ahorro_posible for u in lista),
    )
