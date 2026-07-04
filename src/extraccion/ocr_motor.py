"""Motor OCR de respaldo — envuelve PaddleOCR con los modelos locales v4.

Se usa solo cuando la lectura del QR falla (tarjeta dañada, sucia o deformada),
tal como describe el informe. Los modelos se cargan desde `modelos_ocr/` (offline),
igual que en el script de referencia recuperado/paddle_ocr/probar.py.
"""
import os


class OcrMotor:
    def __init__(self, ruta_modelos: str):
        self.ruta_modelos = ruta_modelos
        self._ocr = None  # carga perezosa: PaddleOCR tarda en inicializar

    def _asegurar_cargado(self):
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR

        det = os.path.join(self.ruta_modelos, "ch_PP-OCRv4_det_infer")
        rec = os.path.join(self.ruta_modelos, "ch_PP-OCRv4_rec_infer")
        diccionario = os.path.join(self.ruta_modelos, "ppocr_keys_v1.txt")

        # enable_mkldnn=False evita el fallo de oneDNN "fused_conv2d" en algunos CPUs.
        kwargs = dict(use_angle_cls=False, lang="es", show_log=False,
                      enable_mkldnn=False)
        # Usar los modelos locales si están presentes; si no, PaddleOCR los descarga.
        if os.path.isdir(det) and os.path.isdir(rec):
            kwargs.update(det_model_dir=det, rec_model_dir=rec)
            if os.path.exists(diccionario):
                kwargs["rec_char_dict_path"] = diccionario

        try:
            self._ocr = PaddleOCR(**kwargs)
        except TypeError:
            # Compatibilidad con versiones que ya no aceptan show_log.
            kwargs.pop("show_log", None)
            self._ocr = PaddleOCR(**kwargs)

    def leer_lineas(self, imagen_bgr) -> list[str]:
        """Devuelve las líneas de texto reconocidas en la imagen (puede ser vacía)."""
        self._asegurar_cargado()
        resultado = self._ocr.ocr(imagen_bgr, cls=False)
        lineas: list[str] = []
        if not resultado:
            return lineas
        for bloque in resultado:
            if not bloque:
                continue
            for item in bloque:
                # Formato PaddleOCR: [caja, (texto, confianza)]
                try:
                    texto = item[1][0]
                except (TypeError, IndexError):
                    continue
                if texto and texto.strip():
                    lineas.append(texto.strip())
        return lineas
