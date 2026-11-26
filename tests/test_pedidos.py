"""Pruebas de la validación de pedidos nuevos (sin base de datos)."""

from optimizador.pedidos import validar_lineas


def test_pedido_correcto_no_tiene_errores():
    assert validar_lineas([(1, 10), (2, 500)], {1, 2}) == []


def test_pedido_sin_lineas():
    assert validar_lineas([]) == ["El pedido necesita al menos una línea."]


def test_cantidad_fuera_de_rango():
    errores = validar_lineas([(1, 0), (2, 501)], {1, 2})
    assert len(errores) == 2 and all("entre 1 y 500" in e for e in errores)


def test_producto_inexistente_y_repetido():
    errores = validar_lineas([(1, 5), (99, 5), (1, 5)], {1})
    assert any("99 no existe" in e for e in errores)
    assert any("repetido" in e for e in errores)
