from datetime import date

from src.siat.periodo import fecha_declaracion


def test_periodo_explicito():
    assert fecha_declaracion("7/2026") == "01/07/2026"
    assert fecha_declaracion("07/2026") == "01/07/2026"
    assert fecha_declaracion("07-2026") == "01/07/2026"  # tolera guion


def test_periodo_por_defecto_es_mes_actual():
    hoy = date.today()
    esperado = f"01/{hoy.month:02d}/{hoy.year}"
    assert fecha_declaracion() == esperado
    assert fecha_declaracion("") == esperado


def test_fecha_declaracion_es_valida():
    # Debe tener formato dd/mm/aaaa que el validador acepta.
    from datetime import datetime
    datetime.strptime(fecha_declaracion(), "%d/%m/%Y")
