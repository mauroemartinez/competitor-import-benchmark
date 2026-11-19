"""Tablero para explorar el análisis: elegís contra qué rivales, qué producto y qué período.

uso: streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from competencia import analisis as a
from competencia import formato as f
from competencia import graficos as g
from competencia.datos import REGISTROS, YO, generar
from competencia.marca import (
    BUENO, CSS_FONDO, CSS_VIDRIO, FUENTES_URL, MALO, TENUE, TEXTO, TINTA_2, TITULOS, colores_empresas,
)

st.set_page_config(page_title="A qué precio importa tu competencia | GlobalAIze", layout="wide")

st.markdown(
    f"""
<style>
@import url('{FUENTES_URL}');
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"], button, input, label {{
  font-family: {TEXTO} !important;
}}
.stApp {{ {CSS_FONDO} }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: rgb(5 30 69 / .55); border-right: 1px solid rgb(235 245 255 / .10); }}
h1, h2, h3 {{ font-family: {TITULOS} !important; font-weight: 500 !important; letter-spacing: -0.01em; }}
h1 {{ font-size: 2.6rem !important; line-height: 1.1 !important; }}
.bajada {{ color: {TINTA_2}; font-size: 1.08rem; max-width: 70ch; margin: -4px 0 18px; }}
.cifra {{ {CSS_VIDRIO} padding: 16px 18px; height: 100%; }}
.cifra h4 {{ font: 500 .92rem/1.3 {TEXTO}; color: {TINTA_2}; margin: 0; padding: 0; }}
.cifra strong {{ display: block; font: 500 1.9rem/1.2 {TITULOS}; margin: 6px 0 4px; }}
.cifra p {{ color: {TENUE}; font-size: .88rem; line-height: 1.35; margin: 0; }}
.cifra p.bueno {{ color: {BUENO}; }} .cifra p.malo {{ color: {MALO}; }}
.nota {{ color: {TINTA_2}; max-width: 72ch; }}
[data-testid="stTabs"] button p {{ font-size: 1rem; }}
[data-testid="stPlotlyChart"] {{ {CSS_VIDRIO} padding: 0; overflow: hidden; }}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def cargar() -> pd.DataFrame:
    if not REGISTROS.exists():
        registros, reales = generar()
        REGISTROS.parent.mkdir(exist_ok=True)
        registros.to_csv(REGISTROS, index=False)
        reales.to_csv(REGISTROS.parent / "valores_reales.csv", index=False)
    return a.cargar()


datos = cargar()
empresas = list(datos.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False).index)
colores_todos = colores_empresas(empresas, YO)
rivales_todos = [e for e in empresas if e != YO]
meses = list(pd.period_range(datos["mes"].min(), datos["mes"].max(), freq="M"))

with st.sidebar:
    st.markdown("### Qué comparar")
    rivales = st.multiselect("Rivales", rivales_todos, default=rivales_todos)
    desde, hasta = st.select_slider(
        "Período", options=meses, value=(meses[-12], meses[-1]), format_func=lambda m: m.strftime("%m/%Y"),
    )
    productos = sorted(datos["producto"].unique())
    st.caption("Datos 100 % sintéticos: empresas, marcas, modelos y precios inventados.")
    st.markdown("[GlobalAIze](https://www.globalaize.com) · [Código](https://github.com/mauroemartinez/competitor-import-benchmark)")

if not rivales:
    st.warning("Elegí al menos un rival para comparar.")
    st.stop()

elegidas = [YO, *rivales]
colores = {e: colores_todos[e] for e in elegidas}
vista = datos[datos["importador"].isin(elegidas)]
periodo = vista[(vista["mes"] >= desde) & (vista["mes"] <= hasta)]

st.markdown("# A qué precio importa tu competencia")
st.markdown(
    f"<p class='bajada'>Herramientas eléctricas de proveedores chinos, de {desde.strftime('%m/%Y')} a "
    f"{hasta.strftime('%m/%Y')}. Tu empresa contra {len(rivales)} {'rival' if len(rivales) == 1 else 'rivales'}.</p>",
    unsafe_allow_html=True,
)

# Las cuatro cifras, sobre el período y los rivales elegidos.
fob = periodo.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False)
lista = a.umbrales(periodo, YO)
puesto = list(fob.index).index(YO) + 1 if YO in fob.index else None
caros = [u for u in lista if u.diferencia > 0.0005]
cifras = [
    ("Tu participación", f.pct(fob.get(YO, 0) / fob.sum()) if len(fob) else "s/d", "del FOB entre las empresas elegidas", ""),
    ("Tu puesto", f"{f.puesto(puesto)} de {len(fob)}" if puesto else "s/d",
     f"detrás de {fob.index[0]}" if puesto and puesto > 1 else "el que más importa", ""),
    ("Pagás más en", f"{len(caros)} de {len(lista)}", "productos, contra el rival que mejor compra cada uno", ""),
    ("Ahorro posible", f.usd(sum(u.ahorro_posible for u in lista)), "al precio del mejor rival, en el período", ""),
]
for columna, (titulo, valor, detalle, tono) in zip(st.columns(4), cifras):
    columna.markdown(
        f"<div class='cifra'><h4>{titulo}</h4><strong>{valor}</strong><p class='{tono}'>{detalle}</p></div>",
        unsafe_allow_html=True,
    )
st.write("")

cotizacion, precios, mercado, compras, registros = st.tabs(
    ["Tu próxima cotización", "Precios", "Participación", "Cómo compra cada uno", "Registros"]
)
config = {"displayModeBar": False}

with cotizacion:
    st.markdown(
        "<p class='nota'>Precio FOB por unidad en el período, tuyo y del rival que mejor compra cada producto. "
        "Ese precio es tu umbral para negociar.</p>",
        unsafe_allow_html=True,
    )
    tabla = pd.DataFrame([
        {
            "Producto": u.producto,
            "Tu precio": f.usd(u.tu_precio, 2),
            "Mejor rival": u.mejor_rival,
            "Su precio": f.usd(u.su_precio, 2),
            "Diferencia": f"{f.flecha(u.diferencia)} {f.pct(u.diferencia, signo=True)}",
            "Para negociar": (f"Arriba de {f.usd(u.su_precio, 2)} pagás más que {u.mejor_rival}" if u.diferencia > 0.0005
                              else "Ya comprás mejor que todos" if u.diferencia < -0.0005
                              else f"Pagás lo mismo que {u.mejor_rival}"),
            "Ahorro posible": f.usd(u.ahorro_posible) if u.ahorro_posible else "",
        }
        for u in lista
    ])
    st.dataframe(tabla, hide_index=True, width="stretch")
    st.plotly_chart(g.precios_relativos(a.precios(periodo), colores, YO), width="stretch", config=config)

with precios:
    defecto = lista[0].producto if lista else productos[0]
    producto = st.selectbox("Producto", productos, index=productos.index(defecto))
    mejor = next((u.mejor_rival for u in lista if u.producto == producto), None)
    st.plotly_chart(
        g.precio_mensual(a.precio_mensual(vista, producto), colores, YO, destacar=mejor),
        width="stretch", config=config,
    )
    st.markdown(
        "<p class='nota'>Todo el historial, para ver la tendencia. Tu empresa y el rival que mejor compra "
        "ese producto en el período quedan marcados.</p>",
        unsafe_allow_html=True,
    )

with mercado:
    st.plotly_chart(g.participacion(a.participacion_movil(vista), colores, YO), width="stretch", config=config)
    st.markdown(
        "<p class='nota'>Participación en el FOB entre las empresas elegidas, sobre los últimos 6 meses de cada punto. "
        "Todo el historial, para ver la tendencia.</p>",
        unsafe_allow_html=True,
    )

with compras:
    izquierda, derecha = st.columns(2)
    izquierda.plotly_chart(g.como_compra(a.como_compra(periodo), colores, YO), width="stretch", config=config)
    derecha.plotly_chart(g.mezcla(a.mezcla(periodo), YO), width="stretch", config=config)
    resumen = a.como_compra(periodo).set_index("importador").loc[[e for e in elegidas if e in fob.index]]
    resumen.index.name = "Empresa"
    st.dataframe(
        pd.DataFrame({
            "Embarques por año": resumen["embarques_por_anio"].map(f.numero),
            "Unidades por embarque": resumen["unidades_por_embarque"].map(f.numero),
            "Días entre compras": resumen["dias_entre_compras"].map(f.numero),
            "FOB": resumen["fob_total"].map(f.usd),
            "Flete y seguro sobre el FOB": resumen["flete_y_seguro"].map(f.pct),
        }),
        width="stretch",
    )

with registros:
    columnas = ["fecha_oficializacion", "destinacion", "item", "subitem", "importador", "producto", "modelo",
                "cantidad", "fob_usd", "fob_asignado", "cif_asignado", "valor_concentrado"]
    st.markdown(
        "<p class='nota'>Las líneas del período, con el producto reconocido y el valor repartido. "
        "En las líneas con valor concentrado, el FOB declarado está entero en otra línea del mismo ítem.</p>",
        unsafe_allow_html=True,
    )
    st.dataframe(periodo[columnas].sort_values("fecha_oficializacion", ascending=False), hide_index=True,
                 width="stretch", height=420)
    st.download_button(
        "Descargar CSV", periodo[columnas].to_csv(index=False).encode("utf-8"),
        file_name="importaciones_periodo.csv", mime="text/csv",
    )
