"""Guardado de una solución en Planificaciones, Rutas y ParadasRuta.

Además asigna a cada viaje:
    * un vehículo real del tipo elegido (el camión k de la flota calculada es
      el k-ésimo vehículo de ese tipo en la tabla Vehiculos), y
    * un conductor de la tabla Conductores que haya descansado al menos el
      descanso diario (11 h) desde su viaje anterior.
Si no hay vehículos o conductores suficientes, la ruta queda sin asignar (NULL).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from .modelo import Escenario, Solucion


def asignar_conductores(sol: Solucion, conductores: list[int], descanso_h: float) -> dict[int, int | None]:
    """Devuelve {índice de viaje: IdConductor}. Voraz por hora de salida."""
    libre: dict[int, datetime] = {}                       # conductor -> cuándo puede volver a conducir
    asignacion: dict[int, int | None] = {}
    for k in sorted(range(len(sol.viajes)), key=lambda i: sol.viajes[i].salida):
        v = sol.viajes[k]
        candidato = next((c for c in conductores if libre.get(c, datetime.min) <= v.salida), None)
        asignacion[k] = candidato
        if candidato is not None:
            libre[candidato] = v.regreso + timedelta(hours=descanso_h)
    return asignacion


def guardar_solucion(conn, esc: Escenario, sol: Solucion, notas: str = "") -> int:
    """Inserta la planificación con sus rutas y paradas. Devuelve el IdPlanificacion."""
    with conn.cursor() as cur:
        cur.execute("SELECT IdVehiculo FROM Vehiculos WHERE IdTipoVehiculo = %s AND Estado <> 'Baja' "
                    "ORDER BY IdVehiculo", (esc.tipo.id,))
        vehiculos = [r["IdVehiculo"] for r in cur.fetchall()]
        cur.execute("SELECT IdConductor FROM Conductores WHERE Activo = 1 ORDER BY IdConductor")
        conductores = [r["IdConductor"] for r in cur.fetchall()]
        conductor_de = asignar_conductores(sol, conductores, esc.params.descanso_diario_h)

        cur.execute(
            "INSERT INTO Planificaciones (IdEscenario, IdAlmacen, IdTipoVehiculo, Algoritmo, "
            "ParametrosAlgoritmo, TiempoCalculoSeg, Notas) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (esc.id, esc.almacen.id, esc.tipo.id, sol.algoritmo, json.dumps(sol.parametros_algoritmo),
             round(sol.tiempo_calculo_s, 3), notas[:500] or None))
        id_plan = cur.lastrowid

        for num_camion, indices in enumerate(sol.camiones, start=1):
            id_vehiculo = vehiculos[num_camion - 1] if num_camion <= len(vehiculos) else None
            for num_viaje, k in enumerate(indices, start=1):
                v = sol.viajes[k]
                cur.execute(
                    "INSERT INTO Rutas (IdPlanificacion, NumCamion, NumViaje, IdVehiculo, IdConductor, FechaSalida, "
                    "FechaRegreso, UnidadesCargadas, KmTotales, HorasConduccion, LitrosCombustible, CosteCombustible, "
                    "CostePeajes, CosteConductor, CosteDietas, CosteMantenimiento, CosteFijoImputado, KgCO2) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (id_plan, num_camion, num_viaje, id_vehiculo, conductor_de.get(k), v.salida, v.regreso,
                     v.unidades, round(v.km_total, 2), round(v.horas_conduccion, 2), round(v.litros, 2),
                     round(v.coste_combustible, 2), round(v.coste_peajes, 2), round(v.coste_conductor, 2),
                     round(v.coste_dietas, 2), round(v.coste_mantenimiento, 2), round(v.coste_fijo, 2),
                     round(v.kg_co2, 2)))
                id_ruta = cur.lastrowid
                cur.executemany(
                    "INSERT INTO ParadasRuta (IdRuta, Orden, IdPedido, IdDestino, KmDesdeAnterior, "
                    "LlegadaPrevista, SalidaPrevista, FechaCaducidadPedido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [(id_ruta, orden, x.pedido.id, x.pedido.id_destino, round(x.km_desde_anterior, 2),
                      x.llegada, x.salida, x.pedido.caducidad) for orden, x in enumerate(v.paradas, start=1)])
    conn.commit()
    return id_plan
