"""Lectura y parseo del código QR del reverso de las tarjetas prepago.

Vía principal de extracción (según el informe): más fiable que el OCR cuando el
QR está legible. El contenido varía por operadora; se soportan dos formatos:

  1. NIT + número de autorización concatenados (caso Entel documentado en el
     motor de Bolifactura): "1020703023300400500600".
  2. URL de consulta del SIAT con querystring: ...?nit=...&numFactura=...&aut=...
"""
import re
from urllib.parse import urlparse, parse_qs

from .datos_fiscales import DatosFiscales
from .extractor_fiscal import (NITS_OPERADORAS, detectar_operadora,
                               _normalizar_numero_factura)

# NIT de cada operadora por nombre (inverso de NITS_OPERADORAS).
_NIT_POR_OPERADORA = {nombre: nit for nit, nombre in NITS_OPERADORAS.items()}

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
    # Formato "NIT + autorización" (todo dígitos, empieza con el NIT de la operadora).
    for nit in NITS_OPERADORAS:
        if texto.startswith(nit):
            datos.nit = nit
            resto = texto[len(nit):]
            if resto:
                datos.autorizacion = resto
            return

    # Formato Entel SFV: autorización (alfanumérica, termina en letra) + N° factura
    # (dígitos finales). Ej.: "123694AEE6991B080355532".
    m = re.fullmatch(r"([0-9A-Z]*[A-Z])(\d{6,})", texto.upper())
    if m:
        datos.autorizacion = m.group(1)
        datos.numero_factura = _normalizar_numero_factura(m.group(2))
        datos.operadora = "ENTEL"          # este formato es propio de Entel
        datos.nit = _NIT_POR_OPERADORA["ENTEL"]  # el QR no trae NIT: se infiere
        return

    # Formato desconocido: guardar todo como autorización para no perder el dato.
    datos.autorizacion = texto


def _variantes_para_qr(imagen_bgr):
    """Versiones preprocesadas de la imagen para mejorar la decodificación del QR.

    En fotos reales (QR pequeño, borroso o con poco contraste) pyzbar falla sobre
    el frame crudo pero sí lee al ampliar, pasar a gris o binarizar.
    """
    yield imagen_bgr
    gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    yield gris
    yield cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    yield cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def leer_qr(imagen_bgr) -> DatosFiscales | None:
    """Decodifica el primer QR de una imagen BGR (OpenCV). None si no hay QR."""
    # 1) pyzbar sobre varias versiones preprocesadas (crudo, gris, ampliado, binario).
    if _zbar_decode is not None:
        for variante in _variantes_para_qr(imagen_bgr):
            for simbolo in _zbar_decode(variante):
                texto = simbolo.data.decode("utf-8", errors="ignore")
                if texto:
                    return parsear_contenido_qr(texto)

    # 2) Respaldo: detector de QR nativo de OpenCV sobre la imagen ampliada.
    detector = cv2.QRCodeDetector()
    ampliada = cv2.resize(imagen_bgr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    texto, _, _ = detector.detectAndDecode(ampliada)
    if texto:
        return parsear_contenido_qr(texto)

    return None
