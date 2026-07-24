from src.siat.atajos import AtajosGlobales


def test_mapea_teclas_a_callbacks():
    eventos = []
    a = AtajosGlobales(al_iniciar=lambda: eventos.append("i"),
                       al_pausar=lambda: eventos.append("p"),
                       al_detener=lambda: eventos.append("d"),
                       backend=object())
    a._procesar_tecla("f8")
    a._procesar_tecla("f7")
    a._procesar_tecla("f9")
    assert eventos == ["i", "p", "d"]


def test_tecla_desconocida_no_hace_nada():
    a = AtajosGlobales(lambda: None, lambda: None, lambda: None, backend=object())
    a._procesar_tecla("a")  # no debe lanzar
