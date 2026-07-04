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


# Regresión: líneas reales del OCR de una tarjeta ENTEL capturada (2026-07-04).
# El número de factura (162452779) va en una etiqueta "FACTURA" sin "N°" y en la
# línea ANTERIOR al rótulo; antes el extractor lo ignoraba.
LINEAS_ENTEL_REAL = [
    "162452779", "FACTURA", "ORIGINAL", "Bs10", "10/11/2029",
    "Raspe con cuidado", "FCHALEN 1/1/2027", "60349064", "12779",
]


def test_entel_real_extrae_numero_factura_sin_etiqueta_completa():
    d = extraer_de_lineas(LINEAS_ENTEL_REAL)
    assert d.numero_factura == "162452779"
    assert d.importe == "10.00"


# Regresión 2: captura nítida con DroidCam. El rótulo real "N° FACTURA" lo lee el
# OCR como 'NFACTURA' (sin °), y el número va DOS líneas abajo. Antes el extractor
# agarraba el teléfono (2141010) o la autorización (123189) por error.
LINEAS_ENTEL_DROIDCAM = [
    "EMPRESANACIONALDE", "NIT:1020703023", "TELECOMUNICACIONESS.A", "NFACTURA",
    "CASA MATRiZ:CFedencoZuazo N1771", "162452780",
    "Edil Tower-Zona Central.Tel2141010", "LaPaz-Bolivia", "FACTURA",
    "NAUTORZACON123189FFD1971B", "ORIGINAL", "Bs10", "10/11/2029",
    "Raspe con cuidado", "FECHALMITEDEEMSON11/11/2027", "LOT349064", "12780",
]


def test_entel_droidcam_no_confunde_factura_con_telefono_ni_autorizacion():
    d = extraer_de_lineas(LINEAS_ENTEL_DROIDCAM)
    assert d.nit == "1020703023"
    assert d.numero_factura == "162452780"   # no 2141010 (tel) ni 123189 (autoriz.)
    assert d.importe == "10.00"


def test_nit_mal_leido_se_corrige_por_operadora():
    # OCR leyó mal el NIT (le comió un dígito) pero la tarjeta dice ENTEL.
    lineas = ["ENTEL S.A.", "NIT: 102010302", "FACTURA N°: 162452780",
              "FECHALIMITEDEEMISION: 31/12/2026", "IMPORTE Bs. 10.00"]
    d = extraer_de_lineas(lineas)
    assert d.nit == "1020703023"   # corregido al NIT oficial de Entel


def test_prefiere_fecha_de_emision_sobre_fecha_de_uso():
    # La fecha de uso (2029) aparece primero, pero se debe declarar la de emisión.
    lineas = ["10/11/2029", "Raspe con cuidado",
              "FECHALIMITEDEEMISION:31/12/2026", "otra linea"]
    assert extraer_de_lineas(lineas).fecha == "31/12/2026"


def test_fecha_emision_aunque_ocr_destroce_la_palabra():
    # OCR real de Ovando: "TSION:01/06/2027" (EMISION destrozada) debe reconocerse.
    lineas = ["10/11/2029", "TSION:01/06/2027"]
    assert extraer_de_lineas(lineas).fecha == "01/06/2027"
