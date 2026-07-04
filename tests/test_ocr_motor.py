import os

import numpy as np
import pytest
from PIL import Image, ImageDraw

pytestmark = pytest.mark.ocr

_MODELOS = os.path.join(os.path.dirname(__file__), "..", "modelos_ocr")


def _hay_paddle():
    try:
        import paddleocr  # noqa: F401
        return True
    except Exception:
        return False


def _img_con_texto(texto: str):
    img = Image.new("RGB", (420, 90), "white")
    d = ImageDraw.Draw(img)
    d.text((12, 30), texto, fill="black")
    return np.array(img)[:, :, ::-1].copy()  # RGB -> BGR


@pytest.mark.skipif(not _hay_paddle(), reason="PaddleOCR no instalado")
def test_ocr_lee_lineas_de_una_imagen():
    from src.extraccion.ocr_motor import OcrMotor
    motor = OcrMotor(_MODELOS)
    lineas = motor.leer_lineas(_img_con_texto("NIT 1020703023"))
    assert isinstance(lineas, list)
    texto = " ".join(lineas)
    assert "1020703023" in texto.replace(" ", "")


@pytest.mark.skipif(not _hay_paddle(), reason="PaddleOCR no instalado")
def test_imagen_en_blanco_devuelve_lista():
    from src.extraccion.ocr_motor import OcrMotor
    motor = OcrMotor(_MODELOS)
    lineas = motor.leer_lineas(np.full((80, 200, 3), 255, dtype=np.uint8))
    assert isinstance(lineas, list)
