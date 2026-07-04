import numpy as np
import qrcode
import cv2

from src.extraccion.pipeline import PipelineExtraccion


def _img_qr(payload: str):
    pil = qrcode.make(payload).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


class _OcrFalso:
    def __init__(self, lineas):
        self._lineas = lineas

    def leer_lineas(self, imagen_bgr):
        return self._lineas


def test_pipeline_usa_qr_cuando_esta_completo():
    # QR con NIT+autorización, y OCR falso que aporta el resto de campos.
    ocr = _OcrFalso(["FACTURA N°: 104827", "FECHA: 31/12/2026", "IMPORTE Bs. 10.00"])
    pipe = PipelineExtraccion(ocr_motor=ocr)
    res = pipe.procesar_imagen(_img_qr("1020703023300400500600"))
    assert res.datos.nit == "1020703023"
    assert res.datos.autorizacion == "300400500600"
    assert res.datos.numero_factura == "104827"   # completado por OCR
    assert res.metodo == "qr+ocr"
    assert res.es_valido


def test_pipeline_cae_a_ocr_si_no_hay_qr():
    ocr = _OcrFalso([
        "ENTEL S.A.", "NIT: 1020703023", "FACTURA N°: 104827",
        "FECHA: 31/12/2026", "IMPORTE Bs. 10.00",
    ])
    pipe = PipelineExtraccion(ocr_motor=ocr)
    res = pipe.procesar_imagen(np.zeros((80, 80, 3), dtype=np.uint8))
    assert res.metodo == "ocr"
    assert res.datos.nit == "1020703023"
    assert res.es_valido


def test_pipeline_sin_datos_devuelve_errores():
    pipe = PipelineExtraccion(ocr_motor=_OcrFalso(["basura sin datos"]))
    res = pipe.procesar_imagen(np.zeros((80, 80, 3), dtype=np.uint8))
    assert not res.es_valido
    assert len(res.errores) > 0
