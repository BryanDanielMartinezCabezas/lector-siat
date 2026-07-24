from src.siat.rellenador import cargar_registro, TecleadorFake, SECUENCIA_RCV, enviar_y_reabrir


def _datos():
    return {"nit": "1020703023", "autorizacion": "123189FFD1971B",
            "numero_factura": "162452780", "fecha": "01/07/2026", "importe": "10.00"}


def test_escribe_los_campos_en_orden():
    t = TecleadorFake()
    cargar_registro(_datos(), t, pausa=0)
    escrituras = [a[1] for a in t.acciones if a[0] == "escribir"]
    # NIT, autorización, N° factura, DUI/DIM(0), DÍA de la fecha(01), importe.
    assert escrituras == ["1020703023", "123189FFD1971B", "162452780",
                          "0", "01", "10.00"]


def test_fecha_escribe_solo_el_dia():
    t = TecleadorFake()
    datos = _datos(); datos["fecha"] = "01/09/2026"
    cargar_registro(datos, t, pausa=0)
    escrituras = [a[1] for a in t.acciones if a[0] == "escribir"]
    assert escrituras[4] == "01"   # solo el día; el mes/año los fija el período


def test_limpia_cada_campo_antes_de_escribir():
    t = TecleadorFake()
    cargar_registro(_datos(), t, pausa=0)
    # Cada campo: seleccionar todo + borrar antes de escribir (6 campos).
    assert sum(1 for a in t.acciones if a[0] == "selall") == len(SECUENCIA_RCV)
    assert sum(1 for a in t.acciones if a[0] == "borrar") == len(SECUENCIA_RCV)


def test_hay_un_tab_entre_cada_campo_pero_no_al_final():
    t = TecleadorFake()
    cargar_registro(_datos(), t, pausa=0)
    tabs = [a for a in t.acciones if a[0] == "tab"]
    assert len(tabs) == len(SECUENCIA_RCV) - 1


def test_campo_vacio_no_rompe():
    t = TecleadorFake()
    datos = _datos(); datos["autorizacion"] = None
    cargar_registro(datos, t, pausa=0)
    escrituras = [a[1] for a in t.acciones if a[0] == "escribir"]
    assert escrituras[1] == ""


class LocalizadorFake:
    def __init__(self, fallar=None):
        self.fallar = fallar or set()
        self.clics = []

    def clic(self, ancla):
        self.clics.append(ancla)
        return ancla not in self.fallar


def test_enviar_y_reabrir_orden_correcto():
    loc = LocalizadorFake()
    assert enviar_y_reabrir(loc, pausa=0) is True
    assert loc.clics == ["adicionar", "nuevo_registro", "nit"]


def test_enviar_y_reabrir_falla_si_no_encuentra_boton():
    loc = LocalizadorFake(fallar={"nuevo_registro"})
    assert enviar_y_reabrir(loc, pausa=0) is False
