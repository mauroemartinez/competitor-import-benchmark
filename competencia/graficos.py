"""Los gráficos del informe y del tablero, con los colores y letras de la marca.

Los mismos gráficos sirven para el informe HTML y para la app, así lo que se
ve en uno es lo que se ve en el otro.
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go

from . import formato as f
from .marca import BORDE, ESCALA, PANEL, REJILLA, TENUE, TEXTO, TINTA, TINTA_2


def _base(fig: go.Figure, alto: int = 380) -> go.Figure:
    eje = dict(gridcolor=REJILLA, zeroline=False, linecolor=BORDE, tickfont=dict(color=TENUE, size=12), title=None, automargin=True)
    fig.update_layout(
        template="none",
        height=alto,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=TEXTO, color=TINTA_2, size=13),
        margin=dict(l=12, r=16, t=12, b=12),
        showlegend=False,
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDE, font=dict(family=TEXTO, color=TINTA, size=13)),
        xaxis=eje,
        yaxis=eje,
        separators=",.",
    )
    return fig


def precios_relativos(tabla: pd.DataFrame, colores: dict[str, str], yo: str) -> go.Figure:
    """Un punto por empresa y producto: cuánto paga contra el promedio del mercado."""
    tabla = tabla.copy()
    promedio = tabla.groupby("producto").apply(lambda g: g["fob"].sum() / g["unidades"].sum(), include_groups=False)
    tabla["contra_promedio"] = tabla["fob_unitario"] / tabla["producto"].map(promedio) - 1
    orden = list(promedio.sort_values().index)
    fig = go.Figure()
    fig.add_vline(x=0, line=dict(color=TENUE, width=1, dash="dot"))
    for empresa in [e for e in colores if e != yo] + [yo]:
        filas = tabla[tabla["importador"] == empresa]
        es_yo = empresa == yo
        fig.add_trace(go.Scatter(
            x=filas["contra_promedio"] * 100,
            y=filas["producto"],
            mode="markers",
            name=empresa,
            marker=dict(
                size=17 if es_yo else 12,
                color=colores[empresa],
                line=dict(color=TINTA if es_yo else "rgba(0,0,0,0)", width=1.5),
                opacity=1 if es_yo else 0.9,
            ),
            customdata=list(zip(filas["fob_unitario"].map(lambda v: f.usd(v, 2)), filas["unidades"].map(f.numero))),
            hovertemplate=f"<b>{empresa}</b><br>%{{y}}<br>%{{customdata[0]}} por unidad<br>%{{x:+.1f}} % contra el promedio<br>%{{customdata[1]}} unidades<extra></extra>",
        ))
    fig = _base(fig, alto=400)
    fig.update_yaxes(categoryorder="array", categoryarray=orden, tickfont=dict(color=TINTA_2, size=13), gridcolor=REJILLA)
    fig.update_xaxes(ticksuffix=" %", zeroline=False)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0, y=1.1, font=dict(color=TINTA_2, size=13)), margin=dict(t=44))
    return fig


def participacion(tabla: pd.DataFrame, colores: dict[str, str], yo: str) -> go.Figure:
    """La participación de cada uno en el tiempo, con el nombre al final de cada línea."""
    fig = go.Figure()
    for empresa in [e for e in colores if e != yo] + [yo]:
        filas = tabla[tabla["importador"] == empresa]
        if filas.empty:
            continue
        es_yo = empresa == yo
        fig.add_trace(go.Scatter(
            x=filas["fecha"], y=filas["en_fob"] * 100, mode="lines", name=empresa,
            line=dict(color=colores[empresa], width=4 if es_yo else 2, shape="spline", smoothing=0.6),
            opacity=1 if es_yo else 0.85,
            hovertemplate=f"<b>{empresa}</b><br>%{{x|%m/%Y}}<br>%{{y:.1f}} % del FOB<extra></extra>",
        ))
    # Los nombres al final de cada línea, separados para que no se pisen.
    finales = tabla.sort_values("fecha").groupby("importador").tail(1).sort_values("en_fob")
    alturas: list[float] = []
    for valor in finales["en_fob"] * 100:
        alturas.append(max(valor, alturas[-1] + 2.4) if alturas else valor)
    for (_, ultimo), altura in zip(finales.iterrows(), alturas):
        empresa = ultimo["importador"]
        fig.add_annotation(
            x=ultimo["fecha"], y=altura, text=f"{empresa} {f.pct(ultimo['en_fob'], 0)}",
            showarrow=False, xanchor="left", xshift=8,
            font=dict(color=colores[empresa] if empresa != yo else TINTA, size=13, family=TEXTO),
        )
    fig = _base(fig, alto=380)
    fig.update_yaxes(ticksuffix=" %", rangemode="tozero")
    fig.update_xaxes(tickformat="%m/%Y")
    fig.update_layout(margin=dict(r=150))
    return fig


def precio_mensual(tabla: pd.DataFrame, colores: dict[str, str], yo: str, destacar: str | None = None) -> go.Figure:
    """El precio FOB unitario de un producto, mes a mes, empresa por empresa.

    Tu empresa y el rival `destacar` van marcados; el resto queda de fondo.
    """
    fig = go.Figure()
    for empresa in [e for e in colores if e != yo] + [yo]:
        filas = tabla[tabla["importador"] == empresa].sort_values("fecha")
        if filas.empty:
            continue
        es_yo = empresa == yo
        fig.add_trace(go.Scatter(
            x=filas["fecha"], y=filas["fob_unitario"], mode="lines+markers", name=empresa,
            line=dict(color=colores[empresa], width=3.5 if es_yo else 1.6),
            marker=dict(size=8 if es_yo else 6, color=colores[empresa]),
            connectgaps=True, opacity=1 if es_yo or destacar in (None, empresa) else 0.35,
            hovertemplate=f"<b>{empresa}</b><br>%{{x|%m/%Y}}<br>USD %{{y:,.2f}} por unidad<extra></extra>",
        ))
    fig = _base(fig, alto=360)
    fig.update_yaxes(tickprefix="USD ", tickformat=",.0f")
    fig.update_xaxes(tickformat="%m/%Y")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0, y=1.12, font=dict(color=TINTA_2, size=13)), margin=dict(t=44))
    return fig


def como_compra(tabla: pd.DataFrame, colores: dict[str, str], yo: str) -> go.Figure:
    """Embarques por año contra unidades por embarque; el tamaño es el FOB total."""
    fig = go.Figure()
    maximo = tabla["fob_total"].max()
    # El nombre va arriba del círculo, o abajo si otro círculo queda muy cerca.
    x = tabla["embarques_por_anio"] / tabla["embarques_por_anio"].max()
    y = tabla["unidades_por_embarque"] / tabla["unidades_por_embarque"].max()
    debajo = set()
    for i in range(len(tabla)):
        for j in range(i):
            if j not in debajo and abs(x.iloc[i] - x.iloc[j]) < 0.15 and abs(y.iloc[i] - y.iloc[j]) < 0.15:
                debajo.add(i if y.iloc[i] < y.iloc[j] else j)
    for i, (_, fila) in enumerate(tabla.iterrows()):
        empresa = fila["importador"]
        fig.add_trace(go.Scatter(
            x=[fila["embarques_por_anio"]], y=[fila["unidades_por_embarque"]], mode="markers+text",
            name=empresa, text=[empresa], textposition="bottom center" if i in debajo else "top center",
            textfont=dict(color=TINTA if empresa == yo else TINTA_2, size=13),
            marker=dict(size=18 + 40 * (fila["fob_total"] / maximo) ** 0.5, color=colores[empresa], opacity=0.85,
                        line=dict(color=TINTA if empresa == yo else "rgba(0,0,0,0)", width=1.5)),
            customdata=[[f.usd(fila["fob_total"]), f.numero(fila["unidades_por_embarque"]), f.numero(fila["embarques_por_anio"])]],
            hovertemplate=f"<b>{empresa}</b><br>%{{customdata[2]}} embarques por año<br>%{{customdata[1]}} unidades por embarque<br>%{{customdata[0]}} FOB<extra></extra>",
        ))
    fig = _base(fig, alto=380)
    fig.update_xaxes(title=dict(text="Embarques por año", font=dict(color=TENUE, size=12)), rangemode="tozero")
    fig.update_yaxes(title=dict(text="Unidades por embarque", font=dict(color=TENUE, size=12)), rangemode="tozero", tickformat=",.0f")
    fig.update_layout(margin=dict(t=24, l=12))
    return fig


def mezcla(matriz: pd.DataFrame, yo: str) -> go.Figure:
    """Qué parte del FOB de cada empresa va a cada producto."""
    # Un producto por fila y una empresa por columna, tu empresa primero.
    columnas = [yo] + [e for e in matriz.index if e != yo]
    matriz = matriz.loc[columnas].T
    texto = matriz.map(lambda v: f.pct(v, 0))
    fig = go.Figure(go.Heatmap(
        z=matriz.values * 100, x=[re.sub(r" ", "<br>", c, count=1) for c in matriz.columns], y=list(matriz.index),
        text=texto.values, texttemplate="%{text}", textfont=dict(color=TINTA, size=13, family=TEXTO),
        # El tope de la escala queda arriba del máximo: la celda más clara sigue
        # siendo legible con el número en blanco.
        colorscale=ESCALA, zmin=0, zmax=float(matriz.values.max()) * 100 * 1.45, showscale=False, xgap=3, ygap=3,
        customdata=[[c for c in matriz.columns] for _ in matriz.index],
        hovertemplate="<b>%{customdata}</b><br>%{y}<br>%{text} de su FOB<extra></extra>",
    ))
    fig = _base(fig, alto=380)
    fig.update_yaxes(autorange="reversed", tickfont=dict(color=TINTA_2, size=13), gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(side="top", tickfont=dict(color=TINTA_2, size=12), gridcolor="rgba(0,0,0,0)", tickangle=0)
    fig.update_layout(margin=dict(t=48, l=8))
    return fig
