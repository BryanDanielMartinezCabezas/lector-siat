import urllib.request
import tarfile
import os

os.makedirs("C:/paddle_models", exist_ok=True)
os.chdir("C:/paddle_models")

# URLs de los modelos (con URL del diccionario corregida)
urls = {
    "deteccion": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar",
    "reconocimiento": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar",
    "diccionario": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.7/ppocr/utils/ppocr_keys_v1.txt"
}

# Descargar
for name, url in urls.items():
    print(f"Descargando {name}...")
    try:
        if name == "diccionario":
            urllib.request.urlretrieve(url, "ppocr_keys_v1.txt")
        else:
            urllib.request.urlretrieve(url, f"ch_PP-OCRv4_{name}.tar")
        print(f"✅ {name} descargado")
    except Exception as e:
        print(f"❌ Error descargando {name}: {e}")

# Extraer tar files
for name in ["deteccion", "reconocimiento"]:
    tar_file = f"ch_PP-OCRv4_{name}.tar"
    if os.path.exists(tar_file):
        print(f"Extrayendo {tar_file}...")
        with tarfile.open(tar_file, "r") as tar:
            tar.extractall()
        print(f"✅ {name} extraído")

print("\n✅ Descarga completada")
print("Archivos en C:/paddle_models:")
print(os.listdir("C:/paddle_models"))