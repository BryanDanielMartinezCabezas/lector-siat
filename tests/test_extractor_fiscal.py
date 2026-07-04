from src.extraccion.extractor_fiscal import extraer_de_lineas, detectar_operadora

LINEAS_ENTEL = [
    "ENTEL S.A.", "NIT: 1020703023", "FACTURA N°:", "000.104.827",
    "AUTORIZACION: 300400500600", "FECHA LIMITE DE EMISION: 31/12/2026",
    "IMPORTE Bs. 10.00", "TARJETA PREPAGO",
]
LINEAS_TIGO = [
    "TELECEL S.A. - TIGO", "N.I.T. 272902028", "NRO = 778588",
    "Telf: 800-17-2000", "FECHA: 05/03/2026", "MONTO A PAGAR Bs 20,00",
]
LINEAS_VIVA = [
    "NUEVATEL PCS DE BOLIVIA S.A.", "NIT 1025260015", "FACTURA N°_:",
    "598786", "26 de abril de 2026", "TOTAL BS: 15.00",
]


def test_entel_extrae_todos_los_campos():
    d = extraer_de_lineas(LINEAS_ENTEL)
    assert d.nit == "1020703023"
    assert d.numero_factura == "104827"      # normaliza puntos y ceros a la izquierda
    assert d.fecha == "31/12/2026"
    assert d.importe == "10.00"
    assert d.operadora == "ENTEL"


def test_tigo_ignora_telefono_y_extrae():
    d = extraer_de_lineas(LINEAS_TIGO)
    assert d.nit == "272902028"
    assert d.numero_factura == "778588"
    assert d.fecha == "05/03/2026"
    assert d.importe == "20.00"              # normaliza coma decimal
    assert d.operadora == "TIGO"


def test_viva_numero_en_linea_siguiente_y_fecha_larga():
    d = extraer_de_lineas(LINEAS_VIVA)
    assert d.nit == "1025260015"
    assert d.numero_factura == "598786"
    assert d.fecha == "26/04/2026"
    assert d.importe == "15.00"
    assert d.operadora == "VIVA"


def test_no_confunde_telefono_con_nit():
    d = extraer_de_lineas(["TELF: 800-17-2000", "SIN MAS DATOS"])
    assert d.nit is None


def test_detectar_operadora_por_texto():
    assert detectar_operadora("recarga TIGO bolivia") == "TIGO"
    assert detectar_operadora("nada que ver") is None


def test_detectar_operadora_por_nit_en_texto():
    assert detectar_operadora("emisor 1025260015 gracias") == "VIVA"
