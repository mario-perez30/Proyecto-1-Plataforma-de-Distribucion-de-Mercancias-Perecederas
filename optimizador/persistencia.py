"""Guardado de una solución en Planificaciones, Rutas y ParadasRuta."""

from __future__ import annotations

import json

from .modelo import Escenario, Solucion


def guardar_solucion(conn, esc: Escenario, sol: Solucion, notas: str = "") -> int:
    """Inserta la planificación con sus rutas y paradas. Devuelve el IdPlanificacion."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO Planificaciones (IdEscenario, IdAlmacen, IdTipoVehiculo, Algoritmo, "
            "ParametrosAlgoritmo, TiempoCalculoSeg, Notas) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (esc.id, esc.almacen.id, esc.tipo.id, sol.algoritmo, json.dumps(sol.parametros_algoritmo),
             round(sol.tiempo_calculo_s, 3), notas[:500] or None))
        id_plan = cur.lastrowid

        for num_camion, indices in enumerate(sol.camiones, start=1):
            for num_viaje, k in enumerate(indices, start=1):
                v = sol.viajes[k]
                cur.execute(
                    "INSERT INTO Rutas (IdPlanificacion, NumCamion, NumViaje, FechaSalida, FechaRegreso, "
                    "UnidadesCargadas, KmTotales, HorasConduccion, LitrosCombustible, CosteCombustible, "
                    "CostePeajes, CosteConductor, CosteDietas, CosteMantenimiento, CosteFijoImputado, KgCO2) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (id_plan, num_camion, num_viaje, v.salida, v.regreso, v.unidades, round(v.km_total, 2),
                     round(v.horas_conduccion, 2), round(v.litros, 2), round(v.coste_combustible, 2),
                     round(v.coste_peajes, 2), round(v.coste_conductor, 2), round(v.coste_dietas, 2),
                     round(v.coste_mantenimiento, 2), round(v.coste_fijo, 2), round(v.kg_co2, 2)))
                id_ruta = cur.lastrowid
                cur.executemany(
                    "INSERT INTO ParadasRuta (IdRuta, Orden, IdPedido, IdDestino, KmDesdeAnterior, "
                    "LlegadaPrevista, SalidaPrevista, FechaCaducidadPedido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [(id_ruta, orden, x.pedido.id, x.pedido.id_destino, round(x.km_desde_anterior, 2),
                      x.llegada, x.salida, x.pedido.caducidad) for orden, x in enumerate(v.paradas, start=1)])
    conn.commit()
    return id_plan
