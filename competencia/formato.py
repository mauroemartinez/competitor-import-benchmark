"""Números con el formato argentino: punto para miles y coma para decimales."""

from __future__ import annotations

import math


def numero(valor: float, decimales: int = 0) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "s/d"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def usd(valor: float, decimales: int = 0) -> str:
    return f"USD {numero(valor, decimales)}"


def pct(valor: float, decimales: int = 1, signo: bool = False) -> str:
    """valor en tanto por uno: 0.234 -> "23,4 %"."""
    if round(valor * 100, decimales) == 0:
        valor = 0.0
    texto = numero(abs(valor) * 100 if signo else valor * 100, decimales)
    if signo:
        return ("" if valor == 0 else "+" if valor > 0 else "-") + texto + " %"
    return texto + " %"


def puntos(valor: float, decimales: int = 1) -> str:
    """Diferencia de participación en puntos: 0.041 -> "4,1 puntos"."""
    return f"{numero(abs(valor) * 100, decimales)} puntos"


def flecha(valor: float, umbral: float = 0.0005) -> str:
    return "▲" if valor > umbral else ("▼" if valor < -umbral else "=")


def puesto(n: int) -> str:
    return f"{n}.º"
