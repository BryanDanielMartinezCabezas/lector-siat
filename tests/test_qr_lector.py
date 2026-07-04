import numpy as np
import qrcode
import cv2

from src.extraccion.qr_lector import leer_qr, parsear_contenido_qr


def _img_qr(payload: str):
    pil = qrcode.make(payload).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def test_parsea_nit_y_autorizacion_seguidos():
    d = parsear_contenido_qr("1020703023300400500600")
    assert d.nit == "1020703023"
    assert d.autorizacion == "300400500600"
    assert d.operadora == "ENTEL"
    assert d.origen == "qr"


def test_parsea_url_siat_con_parametros():
    d = parsear_contenido_qr(
        "https://siat.impuestos.gob.bo/consulta/QR?nit=272902028&numFactura=778588&aut=112233"
    )
    assert d.nit == "272902028"
    assert d.numero_factura == "778588"
    assert d.autorizacion == "112233"


def test_leer_qr_desde_imagen():
    d = leer_qr(_img_qr("1020703023300400500600"))
    assert d is not None
    assert d.nit == "1020703023"


def test_imagen_sin_qr_devuelve_none():
    assert leer_qr(np.zeros((100, 100, 3), dtype=np.uint8)) is None


def test_contenido_vacio_devuelve_none():
    assert parsear_contenido_qr("") is None
