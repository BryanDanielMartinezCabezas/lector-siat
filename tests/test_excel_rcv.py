from openpyxl import load_workbook

from src.siat.excel_rcv import generar_excel_compras, COLUMNAS_RCV


def _tx(numero="104827", importe="100.00", nit="1020703023", aut="300400500600"):
    return {
        "id": "TX-000001", "estado": "pendiente",
        "datos": {
            "nit": nit, "numero_factura": numero, "autorizacion": aut,
            "fecha": "31/12/2026", "importe": importe, "operadora": "ENTEL",
        },
    }


def test_cabeceras_exactas(tmp_path):
    ruta = str(tmp_path / "compras.xlsx")
    generar_excel_compras([_tx()], ruta, razon_social_por_defecto="ENTEL S.A.")
    wb = load_workbook(ruta)
    ws = wb.active
    cabeceras = [c.value for c in ws[1]]
    assert cabeceras == COLUMNAS_RCV


def test_fila_de_datos_y_credito_fiscal_13(tmp_path):
    ruta = str(tmp_path / "compras.xlsx")
    filas = generar_excel_compras([_tx(importe="100.00")], ruta, "ENTEL S.A.")
    assert filas == 1
    ws = load_workbook(ruta).active
    fila = {ws.cell(1, i + 1).value: ws.cell(2, i + 1).value
            for i in range(len(COLUMNAS_RCV))}
    assert str(fila["NIT PROVEEDOR"]) == "1020703023"
    assert str(fila["NUMERO FACTURA"]) == "104827"
    assert float(fila["IMPORTE TOTAL COMPRA"]) == 100.00
    assert float(fila["CREDITO FISCAL"]) == 13.00       # 13% de 100
    assert str(fila["TIPO COMPRA"]) == "1"
    assert str(fila["CODIGO DE CONTROL"]) == "0"
    assert str(fila["ESPECIFICACION"]) == "1"


def test_autorizacion_sin_espacios(tmp_path):
    ruta = str(tmp_path / "compras.xlsx")
    generar_excel_compras([_tx(aut="  300400500600  ")], ruta, "ENTEL S.A.")
    ws = load_workbook(ruta).active
    idx = COLUMNAS_RCV.index("CODIGO DE AUTORIZACION") + 1
    assert ws.cell(2, idx).value == "300400500600"      # recortado


def test_varias_filas(tmp_path):
    ruta = str(tmp_path / "compras.xlsx")
    filas = generar_excel_compras([_tx(), _tx(numero="200"), _tx(numero="300")],
                                  ruta, "ENTEL S.A.")
    assert filas == 3
