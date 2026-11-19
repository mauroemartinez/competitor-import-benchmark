"""Colores y letras de GlobalAIze: los mismos del sitio y del tema oscuro de Power BI.

Un color sigue siempre a la misma empresa en todos los gráficos: tu empresa va
en el cian de la marca y cada rival tiene el suyo, así se reconoce de un vistazo.
"""

FONDO = "#040F23"  # el papel del sitio
PANEL = "#051E45"  # el azul del logo
ELEVADO = "#0D2C5F"
BORDE = "#2A394D"
REJILLA = "#18273C"
TINTA = "#F0EEE9"
TINTA_2 = "#BBC5D1"
TENUE = "#8D9AA8"
BUENO = "#62D286"
MALO = "#EF6661"
CIAN = "#0DA4CF"

# Series en el orden fijo de la marca, sin rojo (queda para "malo") ni naranja.
SERIES = ["#0DA4CF", "#795EC9", "#A69722", "#4170CB", "#3BAB8D", "#B33879"]

# Escala de un solo tono, del cian oscuro al claro, para mapas de calor.
ESCALA = [[0.0, "#00445A"], [0.5, "#0C87AA"], [1.0, "#7ADAF8"]]

TITULOS = "Newsreader, Georgia, serif"
TEXTO = "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif"
FUENTES_URL = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600"
    "&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap"
)

# CSS del vidrio azul de la marca: fondo con tres luces (cian y azul, nunca
# violeta ni naranja) y paneles esmerilados encima.
CSS_FONDO = """
  background:
    radial-gradient(40% 55% at 20% 38%, rgb(34 181 225 / .22), transparent 70%),
    radial-gradient(40% 55% at 82% 78%, rgb(31 79 168 / .30), transparent 70%),
    radial-gradient(45% 35% at 52% 10%, rgb(16 52 140 / .30), transparent 70%),
    #040f23;
  background-attachment: fixed;
"""
CSS_VIDRIO = """
  background: rgb(5 30 69 / .30);
  backdrop-filter: blur(36px) saturate(120%);
  -webkit-backdrop-filter: blur(36px) saturate(120%);
  border: 1.5px solid rgb(235 245 255 / .18);
  border-radius: 14px;
  box-shadow: inset 0 0 14px rgb(170 215 255 / .06), 0 8px 24px rgb(1 6 16 / .45);
"""


def colores_empresas(empresas: list[str], yo: str) -> dict[str, str]:
    """Tu empresa en cian; los rivales en el resto de la paleta, en orden."""
    rivales = [e for e in empresas if e != yo]
    colores = {yo: SERIES[0]}
    for i, rival in enumerate(rivales):
        colores[rival] = SERIES[1 + i % (len(SERIES) - 1)]
    return colores
