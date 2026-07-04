import os
from paddleocr import PaddleOCR

# Rutas absolutas
base_dir = r"C:\Users\Adrian\Desktop\boli_factura\PaddleOcr"
det_model = os.path.join(base_dir, "ch_PP-OCRv4_det_infer")
rec_model = os.path.join(base_dir, "ch_PP-OCRv4_rec_infer")
dict_path = os.path.join(base_dir, "ppocr_keys_v1.txt")

# Verificar archivos
print("Verificando archivos...")
print(f"Detector existe: {os.path.exists(det_model)}")
print(f"Reconocedor existe: {os.path.exists(rec_model)}")
print(f"Diccionario existe: {os.path.exists(dict_path)}")

if not os.path.exists(dict_path):
    print("❌ Diccionario no encontrado. Descargando...")
    import urllib.request
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.7/ppocr/utils/ppocr_keys_v1.txt",
        dict_path
    )
    print("✅ Diccionario descargado")

# Forzar a PaddleOCR a usar tus rutas
ocr = PaddleOCR(
    det_model_dir=det_model,
    rec_model_dir=rec_model,
    rec_char_dict_path=dict_path,
    use_angle_cls=False,
    lang='es',
    show_log=False  # Reduce el ruido
)

print("✅ Modelos cargados correctamente")

# Probar con una imagen (opcional)
# result = ocr.ocr('ruta_a_tu_imagen.jpg')
# print(result)