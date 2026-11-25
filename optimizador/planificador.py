"""Orquestador: de un escenario a una solución completa (viajes + flota)."""

from __future__ import annotations

import time

from .distancias import matriz_km
from .flota import asignar_flota
from .heuristica import clarke_wright
from .modelo import Escenario, Solucion
from .viajes import coste_externalizado, evaluar_viaje

ALGORITMOS = ("directo", "clarke-wright", "ortools")


def matriz_escenario(esc: Escenario) -> list[list[float]]:
    """Matriz de km con el almacén en la posición 0 y el pedido i en la i + 1."""
    puntos = [(esc.almacen.lat, esc.almacen.lon)] + [(p.lat, p.lon) for p in esc.pedidos]
    return matriz_km(puntos, esc.params.factor_carretera)


def planificar(esc: Escenario, algoritmo: str = "ortools", segundos: int = 30,
               coste_fijo_viaje: float = 10_000.0) -> Solucion:
    """Calcula las rutas con el algoritmo elegido y asigna los viajes a camiones.

    algoritmo: "directo" (un camión por pedido, línea base), "clarke-wright" u "ortools".
    """
    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconocido: {algoritmo}. Opciones: {', '.join(ALGORITMOS)}")
    t0 = time.perf_counter()
    km = matriz_escenario(esc)

    if algoritmo == "directo":
        secuencias = [[i] for i in range(len(esc.pedidos))]
    elif algoritmo == "clarke-wright":
        secuencias = clarke_wright(esc, km)
    else:
        from .ortools_vrp import resolver_ortools  # import diferido: OR-Tools es pesado
        secuencias = resolver_ortools(esc, km, segundos=segundos, coste_fijo_viaje=coste_fijo_viaje)

    # Horarios exactos; si un viaje no cumple plazos, se divide en viajes de un pedido
    viajes = []
    for s in secuencias:
        v = evaluar_viaje(s, esc, km)
        if v.factible or len(s) == 1:
            viajes.append(v)
        else:
            viajes += [evaluar_viaje([i], esc, km) for i in s]

    viajes, camiones = asignar_flota(viajes, esc.params)
    return Solucion(
        algoritmo=algoritmo,
        viajes=viajes,
        camiones=camiones,
        tiempo_calculo_s=time.perf_counter() - t0,
        parametros_algoritmo={"segundos": segundos, "coste_fijo_viaje": coste_fijo_viaje,
                              "id_tipo_vehiculo": esc.tipo.id},
        coste_externalizado=coste_externalizado(esc, km),
    )
