"""Pipeline de extracción: QR primero, OCR de respaldo, luego validación.

Orquesta el flujo descrito en el informe sobre una imagen ya capturada:
  1. Intentar decodificar el QR (vía principal).
  2. Si falla o queda incompleto, usar OCR (PaddleOCR) + extractor fiscal.
  3. Validar y devolver los datos junto con la lista de errores.
"""
from dataclasses import dataclass

from .datos_fiscales import DatosFiscales
from .qr_lector import leer_qr
from .extractor_fiscal import extraer_de_lineas
from .validador import validar


@dataclass
class ResultadoLectura:
    datos: DatosFiscales
    errores: list[str]
    metodo: str  # "qr" | "ocr" | "qr+ocr" | "ninguno"

    @property
    def es_valido(self) -> bool:
        return not self.errores


class PipelineExtraccion:
    def __init__(self, ocr_motor=None):
        """ocr_motor: instancia de OcrMotor (perezosa). Si es None, solo QR."""
        self._ocr = ocr_motor

    def procesar_imagen(self, imagen_bgr) -> ResultadoLectura:
        metodo = "ninguno"
        datos = leer_qr(imagen_bgr)
        if datos is not None:
            metodo = "qr"

        # Si el QR no cubrió todos los campos, completar con OCR.
        if (datos is None or datos.campos_faltantes()) and self._ocr is not None:
            lineas = self._ocr.leer_lineas(imagen_bgr)
            datos_ocr = extraer_de_lineas(lineas)
            if datos is None:
                datos = datos_ocr
                metodo = "ocr"
            else:
                datos = _combinar(datos, datos_ocr)
                metodo = "qr+ocr"

        if datos is None:
            datos = DatosFiscales(origen="ocr")

        return ResultadoLectura(datos=datos, errores=validar(datos), metodo=metodo)


def _combinar(base: DatosFiscales, extra: DatosFiscales) -> DatosFiscales:
    """Rellena los campos vacíos de `base` con los de `extra` (QR tiene prioridad)."""
    for campo in ("nit", "numero_factura", "autorizacion", "fecha", "importe", "operadora"):
        if not getattr(base, campo) and getattr(extra, campo):
            setattr(base, campo, getattr(extra, campo))
    return base
