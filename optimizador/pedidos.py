"""Alta de pedidos nuevos.

Inserta el pedido y sus líneas; los triggers de 04_fechas_caducidad.sql calculan
sus totales y sus fechas (fabricación, listo para envío, caducidad y límite de
entrega). Si el destino no está en la matriz por carretera, se calculan sus
tramos con OSRM para que el optimizador siga usando carreteras reales.

Prueba de integración (crea un pedido, lo comprueba y lo deshace):
    python -m optimizador.pedidos --prueba
"""

from __future__ import annotations

import argparse
from datetime import datetime

CANTIDAD_MIN, CANTIDAD_MAX = 1, 500     # restricción CK_LineasPedido_Cantidad
MAX_LINEAS = 32767                      # NumeroLinea es SMALLINT


def validar_lineas(lineas: list[tuple[int, int]], productos_validos: set[int] | None = None) -> list[str]:
    """Errores de las líneas (IdProducto, Cantidad). Lista vacía = correcto."""
    errores = []
    if not lineas:
        errores.append("El pedido necesita al menos una línea.")
    if len(lineas) > MAX_LINEAS:
        errores.append(f"Demasiadas líneas (máximo {MAX_LINEAS}).")
    vistos = set()
    for n, (producto, cantidad) in enumerate(lineas, start=1):
        if not CANTIDAD_MIN <= cantidad <= CANTIDAD_MAX:
            errores.append(f"Línea {n}: la cantidad debe estar entre {CANTIDAD_MIN} y {CANTIDAD_MAX}.")
        if productos_validos is not None and producto not in productos_validos:
            errores.append(f"Línea {n}: el producto {producto} no existe.")
        if producto in vistos:
            errores.append(f"Línea {n}: el producto {producto} está repetido; suma las cantidades en una línea.")
        vistos.add(producto)
    return errores


def crear_pedido(conn, id_cliente: int, id_destino: int, id_escenario: int, lineas: list[tuple[int, int]],
                 fecha: datetime | None = None, prioridad: int = 3, commit: bool = True) -> dict:
    """Crea el pedido con sus líneas y devuelve la fila de Pedidos ya calculada por los triggers.

    Lanza ValueError si los datos no son válidos.
    """
    if not 1 <= prioridad <= 5:
        raise ValueError("La prioridad debe estar entre 1 (máxima) y 5.")
    with conn.cursor() as cur:
        ids = [p for p, _ in lineas]
        validos: set[int] = set()
        if ids:
            cur.execute(f"SELECT IdProducto FROM Productos WHERE IdProducto IN ({', '.join(['%s'] * len(ids))})", ids)
            validos = {r["IdProducto"] for r in cur.fetchall()}
        errores = validar_lineas(lineas, validos)
        for tabla, campo, valor in (("Clientes", "IdCliente", id_cliente), ("Destinos", "IdDestino", id_destino),
                                    ("Escenarios", "IdEscenario", id_escenario)):
            cur.execute(f"SELECT 1 FROM {tabla} WHERE {campo} = %s", (valor,))
            if cur.fetchone() is None:
                errores.append(f"No existe {campo} = {valor}.")
        if errores:
            raise ValueError(" ".join(errores))

        cur.execute("INSERT INTO Pedidos (FechaPedido, IdCliente, IdDestino, IdEscenario, Prioridad) "
                    "VALUES (%s, %s, %s, %s, %s)", (fecha or datetime.now(), id_cliente, id_destino, id_escenario,
                                                    prioridad))
        id_pedido = cur.lastrowid
        cur.executemany("INSERT INTO LineasPedido (IdPedido, NumeroLinea, IdProducto, Cantidad) VALUES (%s, %s, %s, %s)",
                        [(id_pedido, n, p, c) for n, (p, c) in enumerate(lineas, start=1)])
        cur.execute("SELECT * FROM Pedidos WHERE IdPedido = %s", (id_pedido,))
        pedido = cur.fetchone()
    if commit:
        conn.commit()
    return pedido


def asegurar_carretera(conn, id_destino: int) -> bool:
    """Calcula con OSRM los tramos del destino si aún no están en TramosCarretera.

    Devuelve True si el destino queda con todos sus tramos (o ya los tenía).
    """
    from .carreteras import puntos_con_pedidos, tramos_de_punto
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT COUNT(*) AS n FROM TramosCarretera WHERE PuntoOrigen = %s OR PuntoDestino = %s",
                        (id_destino, id_destino))
            tiene = cur.fetchone()["n"]
        except Exception:  # noqa: BLE001 - sin tablas de carreteras (falta el script 06)
            return False
        puntos = puntos_con_pedidos(conn)
        if tiene >= 2 * (len(puntos) - 1):
            return True
        try:
            filas = tramos_de_punto(id_destino, puntos)
        except Exception:  # noqa: BLE001 - sin conexión con OSRM
            return False
        cur.executemany("REPLACE INTO TramosCarretera (PuntoOrigen, PuntoDestino, Km, MinutosCoche, MinutosCamion) "
                        "VALUES (%s, %s, %s, %s, %s)", filas)
    conn.commit()
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m optimizador.pedidos")
    ap.add_argument("--prueba", action="store_true", help="Crea un pedido de prueba, lo comprueba y lo deshace")
    args = ap.parse_args(argv)
    if not args.prueba:
        ap.print_help()
        return 0
    from .datos import conectar
    conn = conectar()
    try:
        pedido = crear_pedido(conn, 1, 1, 1, [(1, 10), (2, 20), (3, 30)], commit=False)
        ok = (pedido["NumLineas"] == 3 and pedido["UnidadesTotales"] == 60
              and pedido["FechaCaducidad"] is not None and pedido["FechaLimiteEntrega"] is not None)
        try:
            crear_pedido(conn, 1, 1, 1, [(1, 600)], commit=False)
            ok = False                                     # debería haber fallado
        except ValueError:
            pass
        print(f"Pedido de prueba {pedido['IdPedido']}: {pedido['NumLineas']} líneas, {pedido['UnidadesTotales']} uds, "
              f"caduca {pedido['FechaCaducidad']} -> {'OK' if ok else 'FALLO'}")
        conn.rollback()
    finally:
        conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
