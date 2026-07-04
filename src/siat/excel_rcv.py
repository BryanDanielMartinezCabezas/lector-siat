"""Generador del archivo Excel de importación masiva del Registro de Compras (RCV).

Vía B de registro en el SIAT (respaldo robusto frente al RPA en vivo, y hoy la
más segura dado que el portal real detecta automatización del navegador). Las
columnas siguen el formato oficial de importación del RCV documentado por el SIN.

IMPORTANTE (regla del proyecto: nos acoplamos a la página): antes del uso real
hay que contrastar estas columnas con el formato descargable vigente del portal,
ya que el SIN lo actualiza. Ver README, sección dry-run.
"""
from openpyxl import Workbook

# Orden oficial de columnas del formato de importación de compras del RCV.
COLUMNAS_RCV = [
    "Nº",
    "ESPECIFICACION",
    "NIT PROVEEDOR",
    "RAZON SOCIAL PROVEEDOR",
    "CODIGO DE AUTORIZACION",
    "NUMERO FACTURA",
    "NUMERO DUI/DIM",
    "FECHA DE FACTURA/DUI/DIM",
    "IMPORTE TOTAL COMPRA",
    "IMPORTE ICE",
    "IMPORTE IEHD",
    "IMPORTE IPJ",
    "TASAS",
    "OTRO NO SUJETO A CREDITO FISCAL",
    "IMPORTES EXENTOS",
    "IMPORTE COMPRAS GRAVADAS A TASA CERO",
    "SUBTOTAL",
    "DESCUENTOS/BONIFICACIONES/REBAJAS SUJETAS AL IVA",
    "IMPORTE GIFT CARD",
    "IMPORTE BASE CF",
    "CREDITO FISCAL",
    "TIPO COMPRA",
    "CODIGO DE CONTROL",
]

_ALICUOTA_IVA = 0.13


def _limpiar(valor) -> str:
    """Sin espacios al inicio/fin: causa de rechazo documentada por el SIN."""
    return str(valor if valor is not None else "").strip()


def generar_excel_compras(
    transacciones: list[dict],
    ruta_salida: str,
    razon_social_por_defecto: str = "",
) -> int:
    """Escribe el Excel de compras y devuelve el número de filas de datos escritas."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Compras"
    ws.append(COLUMNAS_RCV)

    filas = 0
    for i, tx in enumerate(transacciones, start=1):
        d = tx.get("datos", tx)
        try:
            importe = round(float(d.get("importe") or 0), 2)
        except (TypeError, ValueError):
            importe = 0.0
        credito = round(importe * _ALICUOTA_IVA, 2)

        ws.append([
            i,                                        # Nº
            "1",                                      # ESPECIFICACION (fijo)
            _limpiar(d.get("nit")),                   # NIT PROVEEDOR
            _limpiar(d.get("operadora") or razon_social_por_defecto),
            _limpiar(d.get("autorizacion")),          # CODIGO DE AUTORIZACION
            _limpiar(d.get("numero_factura")),        # NUMERO FACTURA
            "",                                       # NUMERO DUI/DIM
            _limpiar(d.get("fecha")),                 # FECHA
            importe,                                   # IMPORTE TOTAL COMPRA
            0, 0, 0, 0, 0, 0, 0,                       # ICE..TASA CERO (no aplican)
            importe,                                   # SUBTOTAL
            0,                                         # DESCUENTOS
            0,                                         # IMPORTE GIFT CARD
            importe,                                   # IMPORTE BASE CF
            credito,                                   # CREDITO FISCAL (13%)
            "1",                                      # TIPO COMPRA
            "0",                                      # CODIGO DE CONTROL (prevaloradas SIAT)
        ])
        filas += 1

    wb.save(ruta_salida)
    return filas
