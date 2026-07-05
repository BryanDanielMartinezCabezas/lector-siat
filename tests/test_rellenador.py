from src.siat.rellenador import cargar_registro, TecleadorFake, SECUENCIA_RCV


def _datos():
    return {"nit": "1020703023", "autorizacion": "123189FFD1971B",
            "numero_factura": "162452780", "fecha": "01/07/2026", "importe": "10.00"}


def test_escribe_los_campos_en_orden_con_tabs():
    t = TecleadorFake()
    cargar_registro(_datos(), t, pausa=0)
    escrituras = [a[1] for a in t.acciones if a[0] == "escribir"]
    # Orden: NIT, autorización, N° factura, DUI/DIM(0), fecha, importe.
    assert escrituras == ["1020703023", "123189FFD1971B", "162452780",
                          "0", "01/07/2026", "10.00"]


def test_hay_un_tab_entre_cada_campo_pero_no_al_final():
    t = TecleadorFake()
    cargar_registro(_datos(), t, pausa=0)
    tabs = [a for a in t.acciones if a[0] == "tab"]
    # 6 campos -> 5 tabs (uno menos que campos).
    assert len(tabs) == len(SECUENCIA_RCV) - 1


def test_campo_vacio_no_rompe():
    t = TecleadorFake()
    datos = _datos(); datos["autorizacion"] = None
    cargar_registro(datos, t, pausa=0)
    escrituras = [a[1] for a in t.acciones if a[0] == "escribir"]
    assert escrituras[1] == ""   # autorización vacía se escribe como cadena vacía
