from mock_siat.servidor import crear_app


def _cliente():
    app = crear_app(lento=False, tasa_error=0.0)
    return app.test_client()


def test_login_tiene_ids_reales_del_siat():
    html = _cliente().get("/").data.decode()
    for sel in ('id="kc-form-login"', 'id="nitCur"', 'id="email"',
                'id="password"', 'id="kc-login"'):
        assert sel in html


def test_login_correcto_redirige_a_menu():
    r = _cliente().post("/login", data={
        "nitCur": "123456789", "email": "a@b.c", "password": "x"})
    assert r.status_code == 302


def test_registro_compra_exitoso_aparece_en_api():
    c = _cliente()
    c.post("/login", data={"nitCur": "1", "email": "a@b.c", "password": "x"})
    r = c.post("/rcv/compras/registro", data={
        "nitProveedor": "1020703023", "codigoAutorizacion": "300400500600",
        "numeroFactura": "104827", "fechaFactura": "31/12/2026",
        "importeTotal": "10.00", "tipoCompra": "1", "codigoControl": "0"})
    assert "mensaje-exito" in r.data.decode()
    registradas = c.get("/api/registradas").json
    assert registradas[0]["numeroFactura"] == "104827"


def test_tasa_error_uno_siempre_falla():
    app = crear_app(lento=False, tasa_error=1.0)
    c = app.test_client()
    c.post("/login", data={"nitCur": "1", "email": "a@b.c", "password": "x"})
    r = c.post("/rcv/compras/registro", data={
        "nitProveedor": "1", "codigoAutorizacion": "1", "numeroFactura": "1",
        "fechaFactura": "01/01/2026", "importeTotal": "1", "tipoCompra": "1",
        "codigoControl": "0"})
    assert "mensaje-error" in r.data.decode()


def test_fallar_en_falla_solo_la_enesima():
    app = crear_app(lento=False, tasa_error=0.0, fallar_en=3)
    c = app.test_client()
    c.post("/login", data={"nitCur": "1", "email": "a@b.c", "password": "x"})

    def registrar(num):
        return c.post("/rcv/compras/registro", data={
            "nitProveedor": "1", "codigoAutorizacion": "1", "numeroFactura": num,
            "fechaFactura": "01/01/2026", "importeTotal": "1", "tipoCompra": "1",
            "codigoControl": "0"}).data.decode()

    assert "mensaje-exito" in registrar("1")
    assert "mensaje-exito" in registrar("2")
    assert "mensaje-error" in registrar("3")   # la tercera falla
    assert "mensaje-exito" in registrar("4")


def test_registro_sin_sesion_redirige_a_login():
    c = _cliente()
    r = c.get("/rcv/compras/registro")
    assert r.status_code == 302
