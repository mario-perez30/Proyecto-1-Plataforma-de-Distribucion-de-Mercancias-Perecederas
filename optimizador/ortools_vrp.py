"""Resolución del problema de rutas con Google OR-Tools.

Modelo (por cada "oleada" de pedidos que están listos a la misma hora):
    * Nodo 0: Mataró. Nodos 1..n: pedidos.
    * Un vehículo por pedido como máximo; cada vehículo usado es un viaje.
    * Coste de cada arco: km x (coste por km + coste del conductor por km), en céntimos.
    * Coste fijo por viaje alto: el solver prioriza usar menos viajes (menos camiones).
    * Dimensión "Carga": unidades del pedido, límite = capacidad del camión.
    * Dimensión "Tiempo" (minutos desde la salida): conducción con un factor que
      incluye pausas y descansos diarios, más el tiempo de descarga. Cada pedido
      tiene como límite su FechaLimiteEntrega.
    * Búsqueda: solución inicial PATH_CHEAPEST_ARC + Guided Local Search con
      límite de tiempo.

Los horarios exactos se recalculan después con evaluar_viaje (reloj del
conductor con el Reglamento 561/2006).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .modelo import Escenario

PENALIZACION_DESCARTE = 10**12   # céntimos: obliga a no descartar pedidos salvo que sea imposible


def factor_tiempo(params) -> float:
    """Horas de reloj por hora de conducción en viajes largos.

    Un día de conducción = 9 h al volante + 1 pausa de 45 min + 11 h de descanso.
    """
    dia = params.conduccion_max_diaria_h + params.pausa_h + params.descanso_diario_h
    return dia / params.conduccion_max_diaria_h


def resolver_ortools(esc: Escenario, km: list[list[float]], segundos: int = 30,
                     coste_fijo_viaje: float = 10_000.0) -> list[list[int]]:
    """Devuelve las secuencias de pedidos (índices de esc.pedidos) de cada viaje."""
    oleadas: dict = defaultdict(list)
    for i, ped in enumerate(esc.pedidos):
        oleadas[ped.listo].append(i)
    rutas: list[list[int]] = []
    for listo in sorted(oleadas):
        rutas += _resolver_oleada(esc, km, oleadas[listo], segundos, coste_fijo_viaje)
    return rutas


def _resolver_oleada(esc: Escenario, km: list[list[float]], indices: list[int],
                     segundos: int, coste_fijo_viaje: float) -> list[list[int]]:
    n = len(indices)
    tipo, p = esc.tipo, esc.params
    salida = esc.pedidos[indices[0]].listo + timedelta(hours=p.carga_h)

    def global_de(nodo: int) -> int:
        """Posición en la matriz km (0 = almacén, i + 1 = pedido i)."""
        return 0 if nodo == 0 else indices[nodo - 1] + 1

    manager = pywrapcp.RoutingIndexManager(n + 1, n, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Coste: km x (€/km sin conductor + €/km del conductor), en céntimos
    eur_km = tipo.coste_km_sin_conductor + p.coste_conductor_h / tipo.velocidad_kmh   # aproximación para el coste

    def coste(desde: int, hasta: int) -> int:
        a, b = manager.IndexToNode(desde), manager.IndexToNode(hasta)
        return int(round(km[global_de(a)][global_de(b)] * eur_km * 100))

    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(coste))
    routing.SetFixedCostOfAllVehicles(int(coste_fijo_viaje * 100))

    # Capacidad
    def demanda(indice: int) -> int:
        nodo = manager.IndexToNode(indice)
        return 0 if nodo == 0 else esc.pedidos[indices[nodo - 1]].unidades

    routing.AddDimensionWithVehicleCapacity(
        routing.RegisterUnaryTransitCallback(demanda), 0, [tipo.capacidad] * n, True, "Carga")

    # Tiempo en minutos desde la salida
    f = factor_tiempo(p)

    def tiempo(desde: int, hasta: int) -> int:
        a, b = manager.IndexToNode(desde), manager.IndexToNode(hasta)
        servicio = 0.0 if a == 0 else esc.pedidos[indices[a - 1]].descarga_h
        ga, gb = global_de(a), global_de(b)
        conduccion = esc.horas[ga][gb] if esc.horas else km[ga][gb] / tipo.velocidad_kmh
        return int(round((servicio + conduccion * f) * 60))

    horizonte = 60 * 24 * 30
    routing.AddDimension(routing.RegisterTransitCallback(tiempo), 0, horizonte, True, "Tiempo")
    dim_tiempo = routing.GetDimensionOrDie("Tiempo")
    for nodo in range(1, n + 1):
        ped = esc.pedidos[indices[nodo - 1]]
        limite_min = int((ped.limite - salida).total_seconds() // 60)
        dim_tiempo.CumulVar(manager.NodeToIndex(nodo)).SetRange(0, max(0, limite_min))
        routing.AddDisjunction([manager.NodeToIndex(nodo)], PENALIZACION_DESCARTE)

    busqueda = pywrapcp.DefaultRoutingSearchParameters()
    busqueda.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    busqueda.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    busqueda.time_limit.seconds = int(segundos)

    solucion = routing.SolveWithParameters(busqueda)
    if solucion is None:
        return [[i] for i in indices]        # sin solución: un viaje por pedido

    rutas: list[list[int]] = []
    visitados: set[int] = set()
    for v in range(n):
        idx = routing.Start(v)
        ruta = []
        while not routing.IsEnd(idx):
            nodo = manager.IndexToNode(idx)
            if nodo != 0:
                ruta.append(indices[nodo - 1])
            idx = solucion.Value(routing.NextVar(idx))
        if ruta:
            rutas.append(ruta)
            visitados.update(ruta)
    # Pedidos descartados por el solver: viaje propio
    rutas += [[i] for i in indices if i not in visitados]
    return rutas
