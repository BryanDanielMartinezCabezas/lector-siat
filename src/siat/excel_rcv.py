from datetime import date
from openpyxl import Workbook

COLUMNAS_RCV = [
    "Nº", "NIT Proveedor", "Código de Autorización", "Número Factura",
    "Número DUI/DIM", "Fecha Factura", "Importe Total Compra", "Importe ICE",
    "Importe IEHD", "Importe IPJ", "Tasas", "Otro No Sujeto a Crédito Fiscal",
    "Importes Exentos", "Importe Compras Gravadas a Tasa Cero", "Subtotal",
    "Descuentos Bonificaciones y Rebajas Sujetas al IVA", "Importe Gift Card",
    "Importe Base Crédito Fiscal", "Crédito Fiscal", "Tipo Compra",
    "Código de Control", "Fecha de Registro",
]
_ALICUOTA_IVA = 0.13


def _limpiar(v) -> str:
    return str(v if v is not None else "").strip()


def generar_excel_compras(transacciones, ruta_salida, razon_social_por_defecto="",
                          fecha_registro=None) -> int:
    hoy = fecha_registro or date.today().strftime("%d/%m/%Y")
    wb = Workbook(); ws = wb.active; ws.title = "Compras"
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
            i, _limpiar(d.get("nit")), _limpiar(d.get("autorizacion")),
            _limpiar(d.get("numero_factura")), "0", _limpiar(d.get("fecha")),
            importe, 0, 0, 0, 0, 0, 0, 0, importe, 0, 0, importe, credito,
            "INTERNO/ACTIVIDAD", "0", hoy,
        ])
        filas += 1
    wb.save(ruta_salida)
    return filas
