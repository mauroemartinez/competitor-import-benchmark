"""Arma el informe HTML: una página sola, con la lectura para compras arriba.

uso: python -m competencia.informe   (escribe docs/index.html)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from jinja2 import Environment

from . import analisis as a
from . import formato as f
from . import graficos as g
from .datos import RAIZ, YO
from .marca import (
    BUENO, CSS_FONDO, CSS_VIDRIO, FONDO, FUENTES_URL, MALO, TENUE, TEXTO, TINTA, TINTA_2,
    TITULOS, colores_empresas,
)

SALIDA = RAIZ / "docs" / "index.html"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def el(producto: str) -> str:
    """'Amoladora 115 mm' -> 'la amoladora 115 mm'."""
    articulo = "la" if producto.startswith("Amoladora") else "el"
    return f"{articulo} {producto[0].lower()}{producto[1:]}"


def del_(producto: str) -> str:
    """'Taladro percutor 850 W' -> 'del taladro percutor 850 W'."""
    texto = el(producto)
    return "del" + texto[2:] if texto.startswith("el ") else "de " + texto


def mes_largo(periodo: pd.Period) -> str:
    return f"{MESES[periodo.month - 1]} de {periodo.year}"


def lectura(datos: pd.DataFrame, yo: str = YO) -> list[str]:
    """Las conclusiones para compras, escritas a partir de los números."""
    ultimos = a.ultimos_meses(datos, 12)
    lista = a.umbrales(ultimos, yo)
    compra = a.como_compra(ultimos).set_index("importador")
    r = a.resumen(datos, yo)
    frases = []

    peor = lista[0]
    frases.append(
        f"En {el(peor.producto)} pagás {f.usd(peor.tu_precio, 2)} por unidad, un {f.pct(peor.diferencia)} más que "
        f"{peor.mejor_rival}, que paga {f.usd(peor.su_precio, 2)}. Si te cotizan arriba de "
        f"{f.usd(peor.su_precio, 2)} FOB, pagás más que él."
    )

    grande = compra["unidades_por_embarque"].idxmax()
    if grande != yo:
        frases.append(
            f"{grande} hace {f.numero(compra.loc[grande, 'embarques_por_anio'])} embarques por año, de "
            f"{f.numero(compra.loc[grande, 'unidades_por_embarque'])} unidades cada uno; vos hacés "
            f"{f.numero(compra.loc[yo, 'embarques_por_anio'])}, de {f.numero(compra.loc[yo, 'unidades_por_embarque'])}. "
            f"Compra menos seguido y en lotes más grandes, y eso se ve en el precio."
        )

    bien = [u for u in lista if u.diferencia < -0.0005]
    if bien:
        nombres = " y ".join(el(u.producto) for u in bien)
        frases.append(f"En {nombres} ya comprás mejor que todos tus rivales: ese precio es tu argumento para negociar el resto.")
    empate = [u for u in lista if abs(u.diferencia) <= 0.0005]
    for u in empate:
        frases.append(f"En {el(u.producto)} pagás lo mismo que {u.mejor_rival}, el que mejor compra.")

    if r.puesto > 1:
        posicion = f"Quedás {f.puesto(r.puesto)} de {r.empresas}, detrás de {r.lider}."
    else:
        posicion = f"Quedás primero, delante de {r.lider}."
    frases.append(
        f"Tu participación en el FOB pasó de {f.pct(r.participacion_anterior)} a {f.pct(r.participacion)} "
        f"en un año. {posicion}"
    )

    caros = [u for u in lista if u.ahorro_posible > 0]
    frases.append(
        f"Si en los {len(caros)} productos donde pagás más hubieras pagado lo que paga el mejor rival, en los últimos 12 meses "
        f"te ahorrabas {f.usd(r.ahorro_posible)}."
    )
    return frases


def construir(datos: pd.DataFrame | None = None, yo: str = YO) -> str:
    datos = a.cargar() if datos is None else datos
    empresas = list(datos.groupby("importador")["fob_asignado"].sum().sort_values(ascending=False).index)
    colores = colores_empresas(empresas, yo)
    ultimos = a.ultimos_meses(datos, 12)
    r = a.resumen(datos, yo)
    lista = a.umbrales(ultimos, yo)
    peor = lista[0].producto
    error = a.error_del_reparto(datos)
    compra = a.como_compra(ultimos)

    figuras = {
        "precios": g.precios_relativos(a.precios(ultimos), colores, yo),
        "evolucion": g.precio_mensual(a.precio_mensual(datos, peor), colores, yo, destacar=lista[0].mejor_rival),
        "participacion": g.participacion(a.participacion_movil(datos), colores, yo),
        "compra": g.como_compra(compra, colores, yo),
        "mezcla": g.mezcla(a.mezcla(ultimos), yo),
    }
    html = {}
    for i, (nombre, figura) in enumerate(figuras.items()):
        html[nombre] = figura.to_html(
            full_html=False, include_plotlyjs="cdn" if i == 0 else False,
            config={"displayModeBar": False, "responsive": True},
        )

    diferencia = r.participacion - r.participacion_anterior
    if r.puesto > 1:
        lider = a.ultimos_meses(datos, 12).groupby("importador")["fob_asignado"].sum()
        distancia = (lider.max() - lider[yo]) / lider.sum()
        sub_puesto = f"a {f.puntos(distancia)} de {r.lider}"
    else:
        sub_puesto = f"delante de {r.lider}"

    cifras = [
        dict(titulo="Tu participación", valor=f.pct(r.participacion),
             detalle=f"{f.flecha(diferencia)} {f.puntos(diferencia)} contra los 12 meses anteriores",
             tono="bueno" if diferencia > 0 else "malo"),
        dict(titulo="Tu puesto", valor=f"{f.puesto(r.puesto)} de {r.empresas}", detalle=sub_puesto, tono=""),
        dict(titulo="Pagás más en", valor=f"{r.productos_mas_caros} de {r.productos}",
             detalle="productos, contra el rival que mejor compra cada uno", tono=""),
        dict(titulo="Ahorro posible", valor=f.usd(r.ahorro_posible),
             detalle="al precio del mejor rival, en 12 meses", tono=""),
    ]
    filas = [
        dict(
            producto=u.producto, tu_precio=f.usd(u.tu_precio, 2), rival=u.mejor_rival, su_precio=f.usd(u.su_precio, 2),
            diferencia=f"{f.flecha(u.diferencia)} {f.pct(u.diferencia, signo=True)}",
            tono="malo" if u.diferencia > 0.0005 else ("bueno" if u.diferencia < -0.0005 else ""),
            umbral=(f"Arriba de {f.usd(u.su_precio, 2)} pagás más que {u.mejor_rival}" if u.diferencia > 0.0005
                    else "Ya comprás mejor que todos" if u.diferencia < -0.0005
                    else f"Pagás lo mismo que {u.mejor_rival}"),
            ahorro=f.usd(u.ahorro_posible) if u.ahorro_posible else "",
        )
        for u in lista
    ]
    periodo = f"de {mes_largo(datos['mes'].min())} a {mes_largo(datos['mes'].max())}"
    marca = _svg(RAIZ / "assets" / "globalaize-mark-dark.svg")
    nombre = _svg(RAIZ / "assets" / "globalaize-wordmark-dark.svg")

    plantilla = Environment(autoescape=False).from_string(PLANTILLA)
    return plantilla.render(
        css_fondo=CSS_FONDO, css_vidrio=CSS_VIDRIO, fuentes=FUENTES_URL, fondo=FONDO, tinta=TINTA,
        tinta_2=TINTA_2, tenue=TENUE, bueno=BUENO, malo=MALO, titulos=TITULOS, texto=TEXTO,
        marca=marca, nombre=nombre, periodo=periodo, cifras=cifras, lectura=lectura(datos, yo), filas=filas,
        figuras=html, peor=del_(peor), rival=lista[0].mejor_rival, empresas=len(empresas), lineas=len(datos),
        destinaciones=datos["destinacion"].nunique(), error=error,
        error_precio=f.pct(error["por_precio"]), error_cantidad=f.pct(error["por_cantidad"]),
    )


def _svg(ruta: Path) -> str:
    """El SVG del logo, sin el comentario ni la declaración XML, para ir dentro del HTML."""
    texto = ruta.read_text(encoding="utf-8")
    texto = re.sub(r"<\?xml.*?\?>", "", texto)
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S).strip()


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A qué precio importa tu competencia | GlobalAIze</title>
<meta name="description" content="Ejemplo con datos sintéticos: a qué precio importa cada rival, tu participación de mercado frente a la suya y qué significa para tu próxima cotización.">
<meta name="theme-color" content="{{ fondo }}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{{ fuentes }}">
<style>
  * { box-sizing: border-box; }
  html { color-scheme: dark; }
  body {
    margin: 0; color: {{ tinta }}; font: 400 16px/1.6 {{ texto }};
    {{ css_fondo }}
  }
  main { max-width: 1120px; margin: 0 auto; padding: 28px 20px 64px; }
  h1, h2, h3 { font-family: {{ titulos }}; font-weight: 500; letter-spacing: -0.01em; line-height: 1.15; margin: 0; }
  h1 { font-size: clamp(2.1rem, 4.6vw, 3.2rem); max-width: 18ch; }
  h2 { font-size: 1.6rem; margin-bottom: 6px; }
  p { margin: 0; }
  a { color: #7adaf8; }
  .marca { display: flex; align-items: center; gap: 10px; margin-bottom: 40px; color: {{ tinta_2 }}; font-size: .95rem; }
  .marca a { display: flex; align-items: center; gap: 10px; text-decoration: none; }
  .marca svg:first-child { height: 34px; width: auto; }
  .marca svg + svg { height: 18px; width: auto; }
  .marca span { margin-left: auto; color: {{ tenue }}; }
  .bajada { color: {{ tinta_2 }}; font-size: 1.12rem; max-width: 62ch; margin: 16px 0 32px; }
  .vidrio { {{ css_vidrio }} padding: 24px; }
  section.vidrio { margin-top: 20px; }
  .nota { color: {{ tinta_2 }}; max-width: 70ch; margin-bottom: 14px; }
  .cifras { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .cifra { padding: 18px 20px; }
  .cifra h3 { font-family: {{ texto }}; font-size: .95rem; font-weight: 500; color: {{ tinta_2 }}; letter-spacing: 0; }
  .cifra strong { display: block; font: 500 2rem/1.2 {{ titulos }}; margin: 8px 0 6px; }
  .cifra p { color: {{ tenue }}; font-size: .9rem; line-height: 1.4; }
  .cifra p.bueno { color: {{ bueno }}; }
  .cifra p.malo { color: {{ malo }}; }
  .lectura ul { margin: 12px 0 0; padding-left: 1.1em; max-width: 78ch; }
  .lectura li { margin: 8px 0; }
  .lectura li::marker { color: #0da4cf; }
  table { width: 100%; border-collapse: collapse; font-size: .97rem; margin-top: 8px; }
  th { text-align: left; font-weight: 500; color: {{ tenue }}; padding: 10px 12px 10px 0; border-bottom: 1px solid rgb(235 245 255 / .14); }
  td { padding: 12px 12px 12px 0; border-bottom: 1px solid rgb(235 245 255 / .08); vertical-align: top; }
  td.num, th.num { text-align: right; white-space: nowrap; }
  td.bueno { color: {{ bueno }}; }
  td.malo { color: {{ malo }}; }
  td.umbral { color: {{ tinta_2 }}; }
  .dos { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
  .dos > .vidrio { margin: 0; }
  .metodo ol { margin: 12px 0 0; padding-left: 1.2em; max-width: 80ch; color: {{ tinta_2 }}; }
  .metodo li { margin: 8px 0; }
  .metodo strong { color: {{ tinta }}; font-weight: 500; }
  footer { margin-top: 36px; color: {{ tenue }}; font-size: .95rem; display: flex; flex-wrap: wrap; gap: 8px 24px; }
  @media (max-width: 900px) {
    .cifras { grid-template-columns: 1fr 1fr; }
    .dos { grid-template-columns: 1fr; }
    .tabla { overflow-x: auto; }
  }
  @media (max-width: 520px) {
    main { padding: 20px 16px 48px; }
    .cifras { grid-template-columns: 1fr; }
    .marca span { display: none; }
  }
</style>
</head>
<body>
<main>
  <header>
    <div class="marca"><a href="https://www.globalaize.com" aria-label="GlobalAIze">{{ marca }}{{ nombre }}</a><span>Datos 100 % sintéticos</span></div>
    <h1>A qué precio importa tu competencia</h1>
    <p class="bajada">Cinco importadores de herramientas eléctricas de proveedores chinos, {{ periodo }}. Con los registros de importación se ve a qué precio compra cada rival, cuánto mercado tiene cada uno y qué significa para tu próxima cotización.</p>
  </header>

  <section class="cifras" aria-label="Las cifras de los últimos 12 meses">
    {% for c in cifras %}
    <div class="vidrio cifra">
      <h3>{{ c.titulo }}</h3>
      <strong>{{ c.valor }}</strong>
      <p class="{{ c.tono }}">{{ c.detalle }}</p>
    </div>
    {% endfor %}
  </section>

  <section class="vidrio lectura">
    <h2>Lectura para compras</h2>
    <ul>
      {% for frase in lectura %}<li>{{ frase }}</li>{% endfor %}
    </ul>
  </section>

  <section class="vidrio">
    <h2>Tu próxima cotización</h2>
    <p class="nota">Precio FOB por unidad de los últimos 12 meses, tuyo y del rival que mejor compra cada producto. Ese precio es tu umbral para negociar.</p>
    <div class="tabla">
    <table>
      <thead><tr><th>Producto</th><th class="num">Tu precio</th><th>Mejor rival</th><th class="num">Su precio</th><th class="num">Diferencia</th><th>Para negociar</th><th class="num">Ahorro posible</th></tr></thead>
      <tbody>
      {% for f in filas %}
        <tr><td>{{ f.producto }}</td><td class="num">{{ f.tu_precio }}</td><td>{{ f.rival }}</td><td class="num">{{ f.su_precio }}</td><td class="num {{ f.tono }}">{{ f.diferencia }}</td><td class="umbral">{{ f.umbral }}</td><td class="num">{{ f.ahorro }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
    </div>
  </section>

  <section class="vidrio">
    <h2>A qué precio compra cada uno</h2>
    <p class="nota">Cada punto es una empresa: a la izquierda de la línea compra más barato que el promedio del mercado, a la derecha, más caro. Tu empresa es el punto más grande.</p>
    {{ figuras.precios }}
  </section>

  <section class="vidrio">
    <h2>Cómo se mueve el precio {{ peor }}</h2>
    <p class="nota">Precio FOB por unidad, mes a mes, con el tuyo y el de {{ rival }} marcados. Los precios de origen bajan con el tiempo; lo que importa es la distancia entre una línea y otra.</p>
    {{ figuras.evolucion }}
  </section>

  <section class="vidrio">
    <h2>Quién gana mercado</h2>
    <p class="nota">Participación de cada empresa en el FOB importado, sobre los últimos 6 meses de cada punto, para que una compra grande no tape la tendencia.</p>
    {{ figuras.participacion }}
  </section>

  <div class="dos">
    <section class="vidrio">
      <h2>Cómo compra cada uno</h2>
      <p class="nota">Cuántos embarques hace por año y de cuántas unidades. El tamaño del círculo es lo que importó en 12 meses.</p>
      {{ figuras.compra }}
    </section>
    <section class="vidrio">
      <h2>Qué trae cada uno</h2>
      <p class="nota">Qué parte de lo que importa cada empresa va a cada producto, en los últimos 12 meses. Cada columna suma 100 %.</p>
      {{ figuras.mezcla }}
    </section>
  </div>

  <section class="vidrio metodo">
    <h2>Cómo lo armamos</h2>
    <ol>
      <li><strong>Reconocer el producto.</strong> Cada empresa escribe la descripción a su manera y cada marca usa sus propios modelos. El producto se reconoce por el tipo y la potencia o la medida, así se compara lo mismo con lo mismo.</li>
      <li><strong>Repartir el valor.</strong> En {{ error.lineas }} líneas el valor del ítem figura entero en otra línea. Lo repartimos por cantidad y por el precio de referencia de cada producto: el error promedio por línea queda en {{ error_precio }}, contra {{ error_cantidad }} si se reparte solo por cantidad. Con datos inventados se puede medir, porque conocemos el valor verdadero.</li>
      <li><strong>Medir.</strong> {{ lineas }} líneas de {{ destinaciones }} destinaciones de {{ empresas }} empresas: precio por unidad, participación, frecuencia, tamaño de lote y mezcla de productos.</li>
    </ol>
    <p class="nota" style="margin-top:14px">Empresas, marcas, modelos y precios son inventados. Con tus importaciones y las de tus rivales, lo implementamos en tu empresa y se actualiza solo cada mes.</p>
  </section>

  <footer>
    <span>Por <a href="https://www.globalaize.com">GlobalAIze</a></span>
    <span><a href="https://github.com/mauroemartinez/competitor-import-benchmark">Código en GitHub</a></span>
  </footer>
</main>
</body>
</html>
"""


def main() -> None:
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(construir(), encoding="utf-8")
    print(f"informe -> {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
