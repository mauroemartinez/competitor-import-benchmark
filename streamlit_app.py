"""Tablero para explorar el análisis: elegís contra qué rivales, qué producto y qué período.

Con la marca de GlobalAIze, en modo claro y oscuro (botón propio, ?tema=claro u ?tema=oscuro).
Lee los datos sintéticos de data/ (si no están, los genera): no necesita archivos externos,
credenciales ni secretos.

uso: streamlit run streamlit_app.py
"""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from competencia import analisis as a
from competencia import formato as f
from competencia import graficos as g
from competencia import marca as m
from competencia.datos import REGISTROS, YO, generar

AQUI = Path(__file__).resolve().parent
REPO = "https://github.com/mauroemartinez/competitor-import-benchmark"

st.set_page_config(
    page_title="A qué precio importa tu competencia | GlobalAIze",
    page_icon=str(AQUI / "assets" / "globalaize-favicon.svg"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Modo claro u oscuro: arranca con el del sistema y se cambia con el botón Oscuro / Claro ──
# (?tema=claro u ?tema=oscuro). Los controles de Streamlit se pintan con CSS, así que todo
# cambia junto aunque el sistema esté en el otro modo.
if st.query_params.get("tema") in ("claro", "oscuro"):
    OSCURO = st.query_params["tema"] == "oscuro"
else:
    try:
        OSCURO = (st.context.theme.type or "dark") != "light"
    except Exception:
        OSCURO = True

if OSCURO:
    C = dict(
        papel="#040F23", tinta="#F0EEE9", secundario="#BBC5D1", tenue="#8D9AA8", eje="#8D9AA8",
        grilla="rgba(255,255,255,0.08)", vidrio="rgb(5 30 69 / .70)", borde="rgb(235 245 255 / .12)",
        canto="rgb(235 245 255 / .34)", sombra="0 8px 24px rgb(1 6 16 / .45)", acento="#1FB5E3",
        bueno="#62D286", malo="#EF6661", hover="#051E45", linea_tabs="#2A394D",
        luces="radial-gradient(40% 55% at 20% 38%, rgb(34 181 225 / .17), transparent 70%),"
              "radial-gradient(40% 55% at 82% 78%, rgb(31 79 168 / .20), transparent 70%),"
              "radial-gradient(45% 35% at 52% 10%, rgb(16 52 140 / .20), transparent 70%), #040F23",
        logo="globalaize-logo-horizontal-es-dark.svg",
    )
else:
    C = dict(
        papel="#F3F1EC", tinta="#051E45", secundario="#3E4E66", tenue="#6B7A8E", eje="#6B7A8E",
        grilla="rgba(5,30,69,0.08)", vidrio="rgb(255 255 255 / .78)", borde="rgb(5 30 69 / .10)",
        canto="rgb(255 255 255 / .95)", sombra="0 8px 24px rgb(5 30 69 / .10)", acento="#1687A9",
        bueno="#299236", malo="#B00A1D", hover="#FFFFFF", linea_tabs="#D3DAE4",
        luces="radial-gradient(40% 55% at 20% 38%, rgb(34 181 225 / .10), transparent 70%),"
              "radial-gradient(40% 55% at 82% 78%, rgb(31 79 168 / .09), transparent 70%), #F3F1EC",
        logo="globalaize-logo-horizontal-es.svg",
    )

# Los gráficos de competencia/graficos.py (compartidos con el informe) vienen en el tema oscuro.
# En el claro se repintan: cada color del oscuro pasa a su par del claro, y la serie de cada
# empresa a la misma serie de la paleta clara de la marca.
CLARO = {
    m.TINTA: "#051E45", m.TINTA_2: "#3E4E66", m.TENUE: "#6B7A8E", m.REJILLA: "rgba(5,30,69,0.08)",
    m.BORDE: "#C9D1DC", m.PANEL: "#FFFFFF",
    "#0DA4CF": "#1687A9", "#795EC9": "#5933AB", "#A69722": "#A3940F", "#4170CB": "#1B4BA9",
    "#3BAB8D": "#199C7E", "#B33879": "#A51069",
}
_CLARO_RE = re.compile("|".join(re.escape(k) for k in CLARO), re.IGNORECASE)
_CLARO_MAYUS = {k.upper(): v for k, v in CLARO.items()}


def pintar(fig: go.Figure) -> go.Figure:
    """Ejes visibles, como en el resto de los tableros de la marca, y en el modo claro los colores del claro."""
    if not any(t.type == "heatmap" for t in fig.data):
        eje = dict(showline=True, linecolor=m.TENUE, linewidth=1.2, ticks="outside", tickcolor=m.TENUE)
        fig.update_xaxes(**eje)
        fig.update_yaxes(**eje)
    if fig.layout.showlegend:  # la leyenda crece hacia arriba, fuera del área de datos, si en el celular ocupa más renglones
        fig.update_layout(legend=dict(yanchor="bottom", y=1.02))
    if fig.layout.xaxis.title.text:  # el título del eje x no entra en el margen de abajo
        fig.update_layout(margin_b=56)
    if OSCURO:
        return fig
    fig = go.Figure(json.loads(_CLARO_RE.sub(lambda x: _CLARO_MAYUS[x.group(0).upper()], fig.to_json())))
    # El mapa de calor conserva su escala de cian: el número va en claro sobre las celdas oscuras.
    fig.update_traces(textfont_color=m.TINTA, selector=dict(type="heatmap"))
    return fig


def _logo() -> str:
    return base64.b64encode((AQUI / "assets" / C["logo"]).read_bytes()).decode()


def _estilos() -> None:
    css = """
<link href="@fuentes_url" rel="stylesheet">
<style>
  .stApp { background: @luces; background-attachment: fixed; color: @tinta; }
  html, body, [class*="st-"], .stMarkdown, .stTabs, button, input, label {
    font-family: "IBM Plex Sans", system-ui, "Segoe UI", sans-serif;
  }
  [data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded" !important; }
  .titulo { font-family: "Newsreader", Georgia, serif !important; font-weight: 500 !important; }
  /* Controles de Streamlit con los colores del tema elegido (pueden diferir del sistema) */
  [data-testid="stWidgetLabel"] p, .stMarkdown, .stMarkdown p, [data-testid="stMarkdownContainer"] { color: @tinta; }
  [data-testid="stButtonGroup"] button { background: @vidrio !important; color: @tinta !important; border-color: @borde !important; }
  [data-testid="stButtonGroup"] button[aria-checked="true"] { color: @acento !important; border-color: @acento !important; }
  [data-testid="stButtonGroup"] button p { color: inherit; }
  [data-baseweb="select"] > div { background: @vidrio !important; border-color: @borde !important; color: @tinta !important; }
  .react-aria-ComboBox > div[role="group"], .react-aria-Select button {
    background: @vidrio !important; border-color: @borde !important; color: @tinta !important;
  }
  .react-aria-ComboBox input, .react-aria-Select button span { color: @tinta !important; }
  .react-aria-ComboBox svg, .react-aria-Select svg { color: @secundario !important; }
  [data-testid="stMultiSelect"] [data-tag] { background: @acento !important; }
  [data-testid="stMultiSelect"] [data-tag] span, [data-testid="stMultiSelect"] [data-tag] svg { color: @papel !important; }
  [data-baseweb="select"] svg { color: @secundario !important; }
  [data-baseweb="select"] input { color: @tinta !important; }
  [data-baseweb="tag"] { background: @acento !important; }
  [data-baseweb="tag"] span, [data-baseweb="tag"] svg { color: @papel !important; }
  [data-baseweb="popover"] ul, [role="listbox"], [role="listbox"] [role="option"] { background: @hover !important; color: @tinta !important; }
  [data-testid="stSlider"] [data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"],
  [data-testid="stSliderTickBarMax"] { color: @secundario !important; }
  [data-testid="stSlider"] [role="slider"] { background: @acento !important; border-color: @acento !important; }
  [data-testid="stAlert"] > div { background: @vidrio; color: @tinta; }
  [data-testid="stDownloadButton"] button { background: @vidrio; color: @tinta; border-color: @borde; }
  [data-testid="stDownloadButton"] button:hover { color: @acento; border-color: @acento; }
  .st-key-tema { width: 100% !important; display: flex; justify-content: flex-end; }
  header[data-testid="stHeader"] { background: transparent; }
  [data-testid="stDecoration"], footer { display: none; }
  .block-container { padding-top: 2.2rem; max-width: 1400px; }
  .encabezado { display: flex; align-items: center; gap: 20px; }
  .encabezado img { height: 52px; width: auto; display: block; }
  .encabezado .titulo { font-size: 2.2rem; color: @tinta; line-height: 1.05; margin: 0; }
  @media (max-width: 900px) {
    .encabezado { flex-wrap: wrap; gap: 12px; } .encabezado img { height: 44px; }
    .encabezado .titulo { font-size: 1.7rem; }
  }
  .bajada { color: @secundario; font-size: 0.95rem; margin: 10px 0 14px; max-width: 80ch; }
  /* Vidrio de la marca: tinte, desenfoque, canto de luz fino (más claro arriba a la izquierda
     y abajo a la derecha), sin brillo, sombra suave y radio 14. */
  .vidrio {
    position: relative; background: @vidrio;
    -webkit-backdrop-filter: blur(36px) saturate(120%); backdrop-filter: blur(36px) saturate(120%);
    border: 1.5px solid @borde; border-radius: 14px; box-shadow: @sombra;
  }
  .vidrio::before {
    content: ""; position: absolute; inset: -1.5px; border-radius: 14px; padding: 1.5px; pointer-events: none;
    background: linear-gradient(135deg, @canto, transparent 28%, transparent 72%, @canto);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
  }
  .tarjetas { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; margin: 8px 0 8px; }
  .tarjeta { padding: 14px 16px; }
  .tarjeta .rotulo { color: @secundario; font-size: 0.76rem; letter-spacing: .04em; text-transform: uppercase; font-weight: 600; }
  .tarjeta .valor { color: @tinta; font-size: 1.65rem; font-weight: 600; margin: 2px 0 6px; white-space: nowrap; }
  .tarjeta .detalle { font-size: 0.82rem; color: @secundario; line-height: 1.45; }
  .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid @linea_tabs; flex-wrap: wrap; }
  .stTabs [data-baseweb="tab"] { color: @secundario; font-weight: 500; padding: 8px 12px; }
  .stTabs [data-baseweb="tab"] p { font-size: 0.98rem; }
  .stTabs [aria-selected="true"] { color: @tinta !important; }
  .stTabs [data-baseweb="tab-highlight"] { background-color: @acento; }
  .stTabs [data-baseweb="tab-border"] { display: none; }
  [data-testid="stTabsScrollLeft"], [data-testid="stTabsScrollRight"] { color: @tinta; }
  [data-testid="stTabsScrollRight"] { background-image: linear-gradient(to right, transparent, @papel 60%) !important; }
  [data-testid="stTabsScrollLeft"] { background-image: linear-gradient(to left, transparent, @papel 60%) !important; }
  /* El gráfico va dentro del vidrio; sin relleno extra, para que no aparezca un scroll de más */
  [data-testid="stPlotlyChart"] {
    background: @vidrio; border: 1.5px solid @borde; border-radius: 14px; box-shadow: @sombra; overflow: hidden;
  }
  .nota { color: @tenue; font-size: 0.85rem; margin: 6px 0 10px; max-width: 80ch; }
  .pie { color: @tenue; font-size: 0.82rem; text-align: center; margin: 28px 0 6px; }
  .pie a, .nota a { color: @acento; }
  .tabla { overflow: auto; padding: 4px 8px; margin-bottom: 12px; }
  .tabla table { width: 100%; border-collapse: collapse; color: @tinta; font-size: 0.88rem; border: none; margin: 0; }
  .tabla td, .tabla th { padding: 8px 12px; border: none; border-bottom: 1px solid @linea_tabs; text-align: left; vertical-align: top; }
  .tabla th { color: @secundario; font-weight: 600; position: sticky; top: 0; background: @hover; }
  .tabla td.n, .tabla th.n { text-align: right; white-space: nowrap; }
  .tabla tr:last-child td { border-bottom: none; }
  .tabla .bueno { color: @bueno; } .tabla .malo { color: @malo; }
  .tabla.ancha table { white-space: nowrap; }
  .tabla.registros { max-height: 440px; }
  .tabla.registros table { font-size: 0.8rem; white-space: nowrap; }
</style>
"""
    valores = {**C, "fuentes_url": m.FUENTES_URL}
    for clave, valor in sorted(valores.items(), key=lambda kv: -len(kv[0])):
        css = css.replace("@" + clave, valor)
    st.markdown(css, unsafe_allow_html=True)


def nota(texto: str) -> None:
    st.markdown(f'<div class="nota">{texto}</div>', unsafe_allow_html=True)


def tabla_html(df: pd.DataFrame, numericas: tuple = (), clases: dict | None = None, extra: str = "") -> str:
    """Tabla de vidrio en HTML: la grilla de Streamlit se dibuja en un canvas y no sigue el tema elegido."""
    clases = clases or {}
    encabezado = "".join(f'<th class="{"n" if c in numericas else ""}">{html.escape(str(c))}</th>' for c in df.columns)
    filas = []
    for i, fila in enumerate(df.itertuples(index=False)):
        celdas = []
        for c, v in zip(df.columns, fila):
            clase = " ".join(x for x in ("n" if c in numericas else "", clases.get((i, c), "")) if x)
            celdas.append(f'<td class="{clase}">{html.escape(str(v))}</td>')
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return (f'<div class="vidrio tabla {extra}"><table><thead><tr>{encabezado}</tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table></div>')


def mostrar(fig: go.Figure) -> None:
    st.plotly_chart(pintar(fig), width="stretch", config={"displayModeBar": False})


@st.cache_data
def cargar() -> pd.DataFrame:
    if not REGISTROS.exists():
        registros, reales = generar()
        REGISTROS.parent.mkdir(exist_ok=True)
        registros.to_csv(REGISTROS, index=False)
        reales.to_csv(REGISTROS.parent / "valores_reales.csv", index=False)
    return a.cargar()


# ══════════════════════════════════════════════════════════════════════════════
_estilos()
datos = cargar()
empresas = list(datos.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False).index)
colores_todos = m.colores_empresas(empresas, YO)
rivales_todos = [e for e in empresas if e != YO]
meses = list(pd.period_range(datos["mes"].min(), datos["mes"].max(), freq="M"))

# Encabezado: logo y título alineados, y a la derecha el tema
izquierda, derecha = st.columns([6, 1.3], vertical_alignment="center")
with izquierda:
    st.markdown(f'<div class="encabezado"><img src="data:image/svg+xml;base64,{_logo()}" alt="GlobalAIze">'
                f'<div class="titulo">A qué precio importa tu competencia</div></div>', unsafe_allow_html=True)
with derecha:
    elegido_tema = st.segmented_control("Tema", ["Oscuro", "Claro"], default="Oscuro" if OSCURO else "Claro",
                                        label_visibility="collapsed", key="tema")
    if elegido_tema and (elegido_tema == "Oscuro") != OSCURO:
        st.query_params["tema"] = "oscuro" if elegido_tema == "Oscuro" else "claro"
        st.rerun()

# Qué comparar: los rivales y el período
col_rivales, col_periodo = st.columns([1.4, 1])
with col_rivales:
    rivales = st.multiselect("Rivales", rivales_todos, default=rivales_todos)
with col_periodo:
    desde, hasta = st.select_slider(
        "Período", options=meses, value=(meses[-12], meses[-1]), format_func=lambda x: x.strftime("%m/%Y"),
    )
productos = sorted(datos["producto"].unique())

if not rivales:
    st.warning("Elegí al menos un rival para comparar.")
    st.stop()

elegidas = [YO, *rivales]
colores = {e: colores_todos[e] for e in elegidas}
vista = datos[datos["importador"].isin(elegidas)]
periodo = vista[(vista["mes"] >= desde) & (vista["mes"] <= hasta)]

st.markdown(
    f"<div class='bajada'>Herramientas eléctricas de proveedores chinos, de <b>{desde.strftime('%m/%Y')}</b> a "
    f"<b>{hasta.strftime('%m/%Y')}</b>. Tu empresa contra {len(rivales)} {'rival' if len(rivales) == 1 else 'rivales'}. "
    "Datos 100 % sintéticos: empresas, marcas, modelos y precios inventados.</div>",
    unsafe_allow_html=True,
)

# Las cuatro cifras, sobre el período y los rivales elegidos.
fob = periodo.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False)
lista = a.umbrales(periodo, YO)
puesto = list(fob.index).index(YO) + 1 if YO in fob.index else None
caros = [u for u in lista if u.diferencia > 0.0005]
cifras = [
    ("Tu participación", f.pct(fob.get(YO, 0) / fob.sum()) if len(fob) else "s/d", "del FOB entre las empresas elegidas"),
    ("Tu puesto", f"{f.puesto(puesto)} de {len(fob)}" if puesto else "s/d",
     f"detrás de {fob.index[0]}" if puesto and puesto > 1 else "el que más importa"),
    ("Pagás más en", f"{len(caros)} de {len(lista)}", "productos, contra el rival que mejor compra cada uno"),
    ("Ahorro posible", f.usd(sum(u.ahorro_posible for u in lista)), "al precio del mejor rival, en el período"),
]
st.markdown('<div class="tarjetas">' + "".join(
    f'<div class="vidrio tarjeta"><div class="rotulo">{titulo}</div><div class="valor">{html.escape(valor)}</div>'
    f'<div class="detalle">{html.escape(detalle)}</div></div>' for titulo, valor, detalle in cifras) + "</div>",
    unsafe_allow_html=True)
st.write("")

cotizacion, precios, mercado, compras, registros = st.tabs(
    ["Tu próxima cotización", "Precios", "Participación", "Cómo compra cada uno", "Registros"]
)

with cotizacion:
    nota("Precio FOB por unidad en el período, tuyo y del rival que mejor compra cada producto. "
         "Ese precio es tu umbral para negociar.")
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
    # Rojo si pagás más que el mejor rival, verde si ya comprás mejor.
    tonos = {(i, "Diferencia"): "malo" if u.diferencia > 0.0005 else "bueno" if u.diferencia < -0.0005 else ""
             for i, u in enumerate(lista)}
    st.markdown(tabla_html(tabla, ("Tu precio", "Su precio", "Diferencia", "Ahorro posible"), tonos, extra="ancha"),
                unsafe_allow_html=True)
    mostrar(g.precios_relativos(a.precios(periodo), colores, YO))
    nota("Cada punto es lo que paga una empresa por un producto, contra el promedio del mercado. "
         "Tu empresa, con el punto más grande.")

with precios:
    defecto = lista[0].producto if lista else productos[0]
    producto = st.selectbox("Producto", productos, index=productos.index(defecto))
    mejor = next((u.mejor_rival for u in lista if u.producto == producto), None)
    mostrar(g.precio_mensual(a.precio_mensual(vista, producto), colores, YO, destacar=mejor))
    nota("Todo el historial, para ver la tendencia. Tu empresa y el rival que mejor compra "
         "ese producto en el período quedan marcados.")

with mercado:
    movil = a.participacion_movil(vista)
    fig = g.participacion(movil, colores, YO)
    # Rango fijo en los datos: si no, en el celular Plotly estira el eje para que entren los nombres del final.
    fig.update_xaxes(range=[movil["fecha"].min(), movil["fecha"].max()])
    mostrar(fig)
    nota("Participación en el FOB entre las empresas elegidas, sobre los últimos 6 meses de cada punto. "
         "Todo el historial, para ver la tendencia.")

with compras:
    izquierda, derecha = st.columns(2)
    with izquierda:
        mostrar(g.como_compra(a.como_compra(periodo), colores, YO))
    with derecha:
        mostrar(g.mezcla(a.mezcla(periodo), YO))
    resumen = a.como_compra(periodo).set_index("importador").loc[[e for e in elegidas if e in fob.index]]
    tabla_compras = pd.DataFrame({
        "Empresa": resumen.index,
        "Embarques por año": resumen["embarques_por_anio"].map(f.numero).values,
        "Unidades por embarque": resumen["unidades_por_embarque"].map(f.numero).values,
        "Días entre compras": resumen["dias_entre_compras"].map(f.numero).values,
        "FOB": resumen["fob_total"].map(f.usd).values,
        "Flete y seguro sobre el FOB": resumen["flete_y_seguro"].map(f.pct).values,
    })
    st.markdown(tabla_html(tabla_compras, tuple(tabla_compras.columns[1:]), extra="ancha"), unsafe_allow_html=True)
    nota("En los círculos, cada empresa: cuántas veces compra por año y cuántas unidades por embarque; "
         "el tamaño es su FOB. En la grilla, qué parte de su FOB va a cada producto.")

with registros:
    columnas = ["fecha_oficializacion", "destinacion", "item", "subitem", "importador", "producto", "modelo",
                "cantidad", "fob_usd", "fob_asignado", "cif_asignado", "valor_concentrado"]
    nota("Las líneas del período, con el producto reconocido y el valor repartido. "
         "En las líneas con valor concentrado, el FOB declarado está entero en otra línea del mismo ítem.")
    lineas = periodo[columnas].sort_values("fecha_oficializacion", ascending=False)
    vista_lineas = pd.DataFrame({
        "Fecha": pd.to_datetime(lineas["fecha_oficializacion"]).dt.strftime("%d/%m/%Y"),
        "Destinación": lineas["destinacion"],
        "Ítem": lineas["item"],
        "Subítem": lineas["subitem"],
        "Importador": lineas["importador"],
        "Producto": lineas["producto"],
        "Modelo": lineas["modelo"],
        "Cantidad": lineas["cantidad"].map(f.numero),
        "FOB declarado": lineas["fob_usd"].map(lambda v: f.numero(v, 2)),
        "FOB repartido": lineas["fob_asignado"].map(lambda v: f.numero(v, 2)),
        "CIF repartido": lineas["cif_asignado"].map(lambda v: f.numero(v, 2)),
        "Valor concentrado": lineas["valor_concentrado"].map(lambda v: "Sí" if v else ""),
    })
    st.markdown(tabla_html(vista_lineas, ("Ítem", "Subítem", "Cantidad", "FOB declarado", "FOB repartido", "CIF repartido"),
                           extra="registros"), unsafe_allow_html=True)
    st.download_button(
        "Descargar CSV del período", lineas.to_csv(index=False).encode("utf-8"),
        file_name="importaciones_periodo.csv", mime="text/csv",
    )
    nota(f"{f.numero(len(lineas))} líneas en el período, de la más nueva a la más vieja. Valores en USD.")

st.markdown(
    '<div class="pie">Globalizate con <a href="https://www.globalaize.com" target="_blank">GlobalAIze</a>. '
    f'Código abierto en <a href="{REPO}" target="_blank">GitHub</a>.</div>',
    unsafe_allow_html=True,
)
