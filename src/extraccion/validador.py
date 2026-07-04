"""Validación de los datos fiscales antes de registrarlos en el Libro Mayor.

Devuelve una lista de mensajes de error en español; lista vacía significa que
los datos pasan todas las reglas.
"""
from datetime import datetime

from .datos_fiscales import DatosFiscales
from .extractor_fiscal import NITS_OPERADORAS


def validar(datos: DatosFiscales) -> list[str]:
    errores: list[str] = []

    # --- NIT: obligatorio, 7 a 11 dígitos ---
    if not datos.nit:
        errores.append("Falta el NIT del emisor.")
    elif not datos.nit.isdigit() or not (7 <= len(datos.nit) <= 11):
        errores.append(f"El NIT '{datos.nit}' no tiene entre 7 y 11 dígitos.")
    elif datos.nit not in NITS_OPERADORAS and not datos.operadora:
        errores.append(
            f"El NIT '{datos.nit}' no corresponde a ninguna operadora conocida "
            "(Entel/Tigo/Viva); revise la operadora."
        )

    # --- Número de factura: obligatorio ---
    if not datos.numero_factura:
        errores.append("Falta el número de factura.")

    # --- Fecha: obligatoria y válida (dd/mm/aaaa) ---
    if not datos.fecha:
        errores.append("Falta la fecha de la factura.")
    else:
        try:
            datetime.strptime(datos.fecha, "%d/%m/%Y")
        except ValueError:
            errores.append(f"La fecha '{datos.fecha}' no es válida (dd/mm/aaaa).")

    # --- Importe: obligatorio, numérico y mayor a cero ---
    if not datos.importe:
        errores.append("Falta el importe.")
    else:
        try:
            if float(datos.importe) <= 0:
                errores.append("El importe debe ser mayor a cero.")
        except ValueError:
            errores.append(f"El importe '{datos.importe}' no es un número válido.")

    return errores
