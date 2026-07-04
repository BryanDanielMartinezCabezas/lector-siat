import json
import os
import threading

import pytest
from werkzeug.serving import make_server


class _ServidorEnHilo:
    def __init__(self, app, port):
        self.srv = make_server("127.0.0.1", port, app, threaded=True)
        self.hilo = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self):
        self.hilo.start()
        return self

    def __exit__(self, *args):
        self.srv.shutdown()


@pytest.fixture
def selectores():
    ruta = os.path.join(os.path.dirname(__file__), "..", "config", "selectores_siat.json")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def mock_server():
    """Levanta el mock (sin lentitud ni errores) en el puerto 5001."""
    from mock_siat.servidor import crear_app
    app = crear_app(lento=False, tasa_error=0.0)
    with _ServidorEnHilo(app, 5001):
        yield "http://127.0.0.1:5001"


@pytest.fixture
def mock_server_falla_tercera():
    """Levanta el mock donde SOLO la tercera compra falla."""
    from mock_siat.servidor import crear_app
    app = crear_app(lento=False, tasa_error=0.0, fallar_en=3)
    with _ServidorEnHilo(app, 5001):
        yield "http://127.0.0.1:5001"
