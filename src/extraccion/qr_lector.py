"""Lectura y parseo del código QR del reverso de las tarjetas prepago.

Vía principal de extracción (según el informe): más fiable que el OCR cuando el
QR está legible. El contenido varía por operadora; se soportan dos formatos:

  1. NIT + número de autorización concatenados (caso Entel documentado en el
     motor de Bolifactura): "1020703023300400500600".
  2. URL de consulta del SIAT con querystring: ...?nit=...&numFactura=...&aut=...
"""
from urllib.parse import urlparse, parse_qs

from .datos_fiscales import DatosFiscales
from .extractor_fiscal import NITS_OPERADORAS, detectar_operadora

try:
    from pyzbar.pyzbar import decode as _zbar_decode
except Exception:  # pragma: no cover - entorno sin DLL de zbar
    _zbar_decode = None

import cv2


def parsear_contenido_qr(texto: str) -> DatosFiscales | None:
    """Convierte el contenido crudo de un QR en DatosFiscales, o None si es vacío."""
    if not texto or not texto.strip():
        return None
    texto = texto.strip()
    datos = DatosFiscales(origen="qr")

    if texto.lower().startswith("http"):
        _parsear_url(texto, datos)
    else:
        _parsear_concatenado(texto, datos)

    datos.operadora = datos.operadora or detectar_operadora(texto)
    return datos


def _parsear_url(texto: str, datos: DatosFiscales) -> None:
    params = parse_qs(urlparse(texto).query)

    def primero(*claves: str) -> str | None:
        for c in claves:
            for clave_real, valor in params.items():
                if clave_real.lower() == c and valor:
                    return valor[0]
        return None

    datos.nit = primero("nit")
    datos.numero_factura = primero("numfactura", "nrofactura", "factura", "num")
    datos.autorizacion = primero("aut", "autorizacion", "cuf")


def _parsear_concatenado(texto: str, datos: DatosFiscales) -> None:
    # Si empieza con el NIT de una operadora conocida, el resto es la autorización.
    for nit in NITS_OPERADORAS:
        if texto.startswith(nit):
            datos.nit = nit
            resto = texto[len(nit):]
            if resto:
                datos.autorizacion = resto
            return
    # Formato desconocido: guardar todo como autorización para no perder el dato.
    datos.autorizacion = texto


def leer_qr(imagen_bgr) -> DatosFiscales | None:
    """Decodifica el primer QR de una imagen BGR (OpenCV). None si no hay QR."""
    # 1) pyzbar (más robusto ante daño/rotación).
    if _zbar_decode is not None:
        for simbolo in _zbar_decode(imagen_bgr):
            texto = simbolo.data.decode("utf-8", errors="ignore")
            if texto:
                return parsear_contenido_qr(texto)

    # 2) Respaldo: detector de QR nativo de OpenCV.
    detector = cv2.QRCodeDetector()
    texto, _, _ = detector.detectAndDecode(imagen_bgr)
    if texto:
        return parsear_contenido_qr(texto)

    return None
