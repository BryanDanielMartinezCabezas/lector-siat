"""Extractor de campos fiscales desde texto OCR de tarjetas prepago bolivianas.

Port a Python del motor v4 de Bolifactura (lib/services/ocr_service.dart). Reúne
las heurísticas ya calibradas para Entel, Tigo y Viva: regex de NIT/fecha/monto/
número de factura, detección de la operadora, y descarte de falsos positivos
(teléfonos, lotes, órdenes, NIT del cliente).
"""
import re
from datetime import datetime

from .datos_fiscales import DatosFiscales

# NITs de las tres operadoras (confirmados en el motor de Bolifactura).
NITS_OPERADORAS = {
    "1020703023": "ENTEL",
    "272902028": "TIGO",
    "1025260015": "VIVA",
}

_RE_NIT_ETIQUETA = re.compile(r"N\.?\s*I\.?\s*T\.?\s*[:=]?\s*(\d{7,11})", re.IGNORECASE)
_RE_NIT_SUELTO = re.compile(r"\b(\d{7,11})\b")
_RE_FECHA = re.compile(r"\b(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})\b")
_RE_FECHA_LARGA = re.compile(
    r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})\b",
    re.IGNORECASE,
)
_MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}
_RE_MONTO_BS = re.compile(r"(?:Bs\.?|BS\.?)\s*:?\s*([\d.,]+)", re.IGNORECASE)
_RE_NUMERO = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d{4,12})")
# Acepta "FACTURA N°:", "FACTURA", "NRO =", "N° FACTURA", "NUMERO DE FACTURA".
_RE_ETIQUETA_FACTURA = re.compile(
    r"\bFACTURA\b|NRO\.?\s*[=:]|N[°º]\s*FACTURA|NUMERO\s*DE\s*FACTURA",
    re.IGNORECASE,
)
_RE_AUTORIZACION = re.compile(
    r"(?:AUTORIZACI[OÓ]N|AUT\.?|C\.?U\.?F\.?)\s*[:=]?\s*([A-Z0-9]{6,})",
    re.IGNORECASE,
)
_PALABRAS_TELEFONO = ("TELF", "TELEF", "TELEFONO", "TELÉFONO", "TEL.", "TEL:", "TEL N")
_NUMEROS_FALSOS = {"1771", "4050", "2289"}


def detectar_operadora(texto: str) -> str | None:
    """Identifica la operadora por su NIT o por palabras clave en el texto."""
    upper = texto.upper()
    for nit, nombre in NITS_OPERADORAS.items():
        if nit in texto:
            return nombre
    if "ENTEL" in upper:
        return "ENTEL"
    if "TIGO" in upper or "TELECEL" in upper:
        return "TIGO"
    if "VIVA" in upper or "NUEVATEL" in upper:
        return "VIVA"
    return None


def _es_telefono(linea: str) -> bool:
    upper = linea.upper()
    return any(p in upper for p in _PALABRAS_TELEFONO)


def _extraer_nit(linea: str) -> str | None:
    if _es_telefono(linea):
        return None
    m = _RE_NIT_ETIQUETA.search(linea)
    if m:
        return m.group(1)
    # NIT de operadora explícito, aunque no lleve etiqueta.
    for nit in NITS_OPERADORAS:
        if nit in linea:
            return nit
    return None


# Fragmentos que el OCR deja de "EMISIÓN" (EMISION, BMISION, EMISTON, TSION...).
_RE_EMISION = re.compile(r"EMIS|MISION|SION")


def _fecha_de_emision(lineas: list[str]) -> str | None:
    """Fecha en una línea que menciona (aunque mal escrita) la emisión."""
    for linea in lineas:
        if _RE_EMISION.search(linea.upper()):
            fecha = _extraer_fecha(linea)
            if fecha:
                return fecha
    return None


def _extraer_fecha(linea: str) -> str | None:
    larga = _RE_FECHA_LARGA.search(linea)
    if larga:
        dia = larga.group(1).zfill(2)
        mes = _MESES[larga.group(2).lower()]
        anio = larga.group(3)
        return f"{dia}/{mes}/{anio}"
    m = _RE_FECHA.search(linea)
    if m:
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
        if len(anio) == 2:
            anio = "20" + anio
        try:
            datetime(int(anio), int(mes), int(dia))
        except ValueError:
            return None
        return f"{dia.zfill(2)}/{mes.zfill(2)}/{anio}"
    return None


def _normalizar_monto(crudo: str) -> str:
    c = crudo.strip()
    # "1.234,50" -> "1234.50"  |  "20,00" -> "20.00"
    if re.search(r",\d{1,2}$", c):
        c = c.replace(".", "").replace(",", ".")
    else:
        c = c.replace(",", "")
    try:
        return f"{float(c):.2f}"
    except ValueError:
        return c


def _extraer_monto(linea: str) -> str | None:
    m = _RE_MONTO_BS.search(linea)
    if m:
        return _normalizar_monto(m.group(1))
    return None


def _normalizar_numero_factura(crudo: str) -> str:
    sin_puntos = crudo.replace(".", "")
    if len(sin_puntos) > 1 and sin_puntos.startswith("0"):
        sin_puntos = sin_puntos.lstrip("0") or "0"
    return sin_puntos


def _es_numero_ignorable(numero: str, contexto: str) -> bool:
    if numero in _NUMEROS_FALSOS:
        return True
    upper = contexto.upper()
    if _es_telefono(contexto) or "LOTE" in upper or "ORDEN" in upper:
        return True
    if numero in NITS_OPERADORAS:
        return True
    return len(numero) >= 20


def extraer_de_lineas(lineas: list[str]) -> DatosFiscales:
    texto_completo = "\n".join(lineas)
    datos = DatosFiscales(origen="ocr")
    datos.operadora = detectar_operadora(texto_completo)

    for i, linea in enumerate(lineas):
        siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""
        upper = linea.upper()

        if datos.nit is None:
            datos.nit = _extraer_nit(linea)

        if datos.fecha is None:
            datos.fecha = _extraer_fecha(linea)

        if datos.importe is None:
            if any(e in upper for e in ("IMPORTE", "MONTO", "TOTAL", "SON:", "BS")):
                datos.importe = _extraer_monto(linea) or _extraer_monto(siguiente)

        if datos.autorizacion is None:
            m = _RE_AUTORIZACION.search(linea)
            if m:
                datos.autorizacion = m.group(1)

    # Preferir la FECHA LÍMITE DE EMISIÓN (la que pide el SIAT) sobre la fecha de
    # uso/vencimiento, que suele aparecer primero. El OCR destroza "EMISIÓN"
    # (EMISION, BMISION, EMISTON, TSION...), por eso se buscan fragmentos.
    fecha_emision = _fecha_de_emision(lineas)
    if fecha_emision:
        datos.fecha = fecha_emision

    # Si la operadora es conocida pero el OCR no leyó el NIT, se infiere.
    if datos.nit is None and datos.operadora:
        for nit, nombre in NITS_OPERADORAS.items():
            if nombre == datos.operadora:
                datos.nit = nit
                break

    # Respaldo del importe: mayor número con decimales cerca de una etiqueta de total.
    if datos.importe is None:
        datos.importe = _importe_de_respaldo(lineas)

    datos.numero_factura = _extraer_numero_factura(lineas, datos)

    return datos


# Rótulo del número de factura ("N° FACTURA", "NFACTURA", "FACTURA N°", "NRO",
# "NUMERO DE FACTURA"). NO incluye la palabra "FACTURA" suelta, para no confundir
# con el teléfono o la autorización que suelen ir junto a ella.
_RE_ROTULO_FACTURA = re.compile(
    r"N\s*[°º]?\s*FACTURA|FACTURA\s*N\s*[°º:]|\bNRO\b|NUMERO\s*DE\s*FACTURA",
    re.IGNORECASE,
)


def _linea_pura_numerica(linea: str) -> str | None:
    """Devuelve el número si la línea es SOLO dígitos (con puntos), 6–12 dígitos."""
    texto = linea.strip()
    if not re.fullmatch(r"\d[\d.]{4,13}", texto):
        return None
    numero = texto.replace(".", "")
    return numero if 6 <= len(numero) <= 12 else None


def _valido_factura(numero: str, contexto: str, datos: DatosFiscales) -> bool:
    if numero == datos.nit:
        return False
    if datos.autorizacion and numero in datos.autorizacion.replace(".", ""):
        return False
    return not _es_numero_ignorable(numero, contexto)


def _extraer_numero_factura(lineas: list[str], datos: DatosFiscales) -> str | None:
    # 1) Junto a un rótulo de factura: número en la misma línea o en la ventana
    #    siguiente (el número real suele ser una línea puramente numérica).
    for i, linea in enumerate(lineas):
        if not _RE_ROTULO_FACTURA.search(linea):
            continue
        resto = _RE_ROTULO_FACTURA.sub(" ", linea)
        m = re.search(r"\d{1,3}(?:\.\d{3})+|\d{6,12}", resto)
        if m:
            numero = m.group(0).replace(".", "")
            if _valido_factura(numero, linea, datos):
                return _normalizar_numero_factura(numero)
        for j in range(i + 1, min(i + 5, len(lineas))):
            numero = _linea_pura_numerica(lineas[j])
            if numero and _valido_factura(numero, lineas[j], datos):
                return _normalizar_numero_factura(numero)

    # 2) Sin rótulo legible: primera línea puramente numérica válida.
    for linea in lineas:
        numero = _linea_pura_numerica(linea)
        if numero and _valido_factura(numero, linea, datos):
            return _normalizar_numero_factura(numero)
    return None


def _importe_de_respaldo(lineas: list[str]) -> str | None:
    mejor = None
    mejor_val = 0.0
    for linea in lineas:
        upper = linea.upper()
        if not any(e in upper for e in ("IMPORTE", "TOTAL", "MONTO", "BS", "PAGAR")):
            continue
        for m in re.finditer(r"\d{1,8}(?:[.,]\d{2})", linea):
            val = float(_normalizar_monto(m.group(0)))
            if mejor_val < val < 999999:
                mejor_val = val
                mejor = _normalizar_monto(m.group(0))
    return mejor
