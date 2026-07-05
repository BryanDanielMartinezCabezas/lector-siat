"""Fecha de declaración para tarjetas prepago.

El ingeniero-cliente (Kevin Díaz) confirmó, viendo el formulario real del RCV, que
las tarjetas prepago NO tienen fecha propia: se declaran con el **01 del mes
vigente** (cualquier fecha del mes en curso sirve). Por eso la fecha para declarar
no es la que trae la tarjeta, sino el primer día del período.
"""
from datetime import date


def fecha_declaracion(periodo: str | None = None) -> str:
    """Devuelve '01/MM/AAAA'. periodo opcional 'MM/AAAA'; si None, usa el mes actual."""
    if periodo:
        partes = periodo.replace("-", "/").split("/")
        if len(partes) == 2:
            mm, aaaa = partes
            return f"01/{int(mm):02d}/{int(aaaa)}"
    hoy = date.today()
    return f"01/{hoy.month:02d}/{hoy.year}"
