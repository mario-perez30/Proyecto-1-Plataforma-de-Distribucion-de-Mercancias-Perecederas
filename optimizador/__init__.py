"""Optimizador de rutas de reparto de IA DELIVERY SL.

Resuelve un problema de rutas de vehículos con capacidad y plazos (CVRP con
ventanas de tiempo) desde Mataró y calcula la flota mínima de camiones propios.

Módulos:
    modelo       Clases de datos (pedidos, vehículos, viajes, soluciones).
    datos        Carga de un escenario desde la base de datos BDIADelivery.
    distancias   Matriz de distancias por carretera (haversine x factor).
    tiempos      Reloj del conductor con el Reglamento (CE) 561/2006.
    viajes       Evaluación de un viaje: horarios, plazos, km, costes y CO2.
    heuristica   Algoritmo de ahorros de Clarke-Wright (línea base).
    ortools_vrp  Resolución con Google OR-Tools.
    flota        Asignación de viajes a camiones: flota mínima.
    persistencia Guardado de la planificación en la base de datos.
    planificador Orquesta todo lo anterior.
"""

__version__ = "0.1.0"
