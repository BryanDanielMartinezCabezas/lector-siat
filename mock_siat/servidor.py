"""Mock local del portal SIAT — réplica FIEL para desarrollo y demo del RPA.

Regla del proyecto: nos acoplamos a la página real. El login replica los ids y la
estética capturados del portal real (referencia_siat/). El formulario de registro
de compras usa los ids del perfil "mock" de config/selectores_siat.json; el día del
dry-run se contrastará con el formulario real logueado y se ajustará.

Simula además el comportamiento hostil del SIAT real: lentitud (2–15 s) y errores
de servidor aleatorios, para probar la resiliencia del ejecutor RPA.
"""
import random
import time

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify)

# Almacén en memoria de las compras aceptadas (reiniciable para las pruebas).
REGISTRADAS: list[dict] = []


def crear_app(lento: bool = True, tasa_error: float = 0.10,
              fallar_en: int | None = None) -> Flask:
    """Crea la app del mock.

    lento: si True, cada registro tarda 2–15 s como el SIAT real.
    tasa_error: probabilidad [0..1] de que un registro devuelva error de servidor.
    fallar_en: si se indica, SOLO la N-ésima compra de la sesión falla (modo
               determinista para probar el "detener todo ante un fallo").
    """
    app = Flask(__name__)
    app.secret_key = "mock-siat-dev"
    app.config["MOCK_LENTO"] = lento
    app.config["MOCK_TASA_ERROR"] = tasa_error
    app.config["MOCK_FALLAR_EN"] = fallar_en

    REGISTRADAS.clear()
    contador = {"n": 0}

    @app.route("/")
    def login():
        return render_template("login.html")

    @app.route("/login", methods=["POST"])
    def hacer_login():
        # El mock acepta cualquier credencial no vacía (no valida contra el SIN).
        if request.form.get("nitCur") and request.form.get("password"):
            session["autenticado"] = True
            return redirect(url_for("menu"))
        return render_template("login.html", error="Complete sus credenciales."), 401

    @app.route("/v2/launcher/")
    def menu():
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return render_template("menu.html")

    @app.route("/rcv/compras/registro", methods=["GET", "POST"])
    def registro_compra():
        if not session.get("autenticado"):
            return redirect(url_for("login"))

        if request.method == "GET":
            return render_template("registro_compra.html")

        # Simular lentitud del SIAT real.
        if app.config["MOCK_LENTO"]:
            time.sleep(random.uniform(2, 15))

        contador["n"] += 1
        falla_determinista = (
            app.config["MOCK_FALLAR_EN"] is not None
            and contador["n"] == app.config["MOCK_FALLAR_EN"]
        )
        falla_aleatoria = random.random() < app.config["MOCK_TASA_ERROR"]

        if falla_determinista or falla_aleatoria:
            return render_template(
                "registro_compra.html",
                error="Error del servidor SIAT. Intente nuevamente más tarde.",
            ), 500

        REGISTRADAS.append({
            "nitProveedor": request.form.get("nitProveedor"),
            "codigoAutorizacion": request.form.get("codigoAutorizacion"),
            "numeroFactura": request.form.get("numeroFactura"),
            "fechaFactura": request.form.get("fechaFactura"),
            "importeTotal": request.form.get("importeTotal"),
            "tipoCompra": request.form.get("tipoCompra"),
            "codigoControl": request.form.get("codigoControl"),
        })
        return render_template(
            "registro_compra.html",
            exito=f"Compra registrada correctamente (N° {request.form.get('numeroFactura')}).",
        )

    @app.route("/api/registradas")
    def api_registradas():
        return jsonify(REGISTRADAS)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    return app


if __name__ == "__main__":
    crear_app(lento=True, tasa_error=0.10).run(host="127.0.0.1", port=5001, debug=False)
