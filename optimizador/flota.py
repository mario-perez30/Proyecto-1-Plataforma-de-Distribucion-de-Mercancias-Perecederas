"""Flota mínima: asignación de viajes a camiones.

Un camión puede hacer varios viajes seguidos: cuando vuelve a Mataró se carga
de nuevo y sale otra vez. Un viaje puede salir más tarde de lo previsto
siempre que ninguna de sus entregas pase su límite (su "holgura").

Algoritmo voraz (best fit):
    1. Ordena los viajes por hora de salida y, a igualdad, por menor holgura.
    2. Para cada viaje, entre los camiones que pueden hacerlo a tiempo elige el
       que queda libre más tarde (aprovecha mejor los huecos).
    3. Si ninguno puede, añade un camión nuevo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .modelo import Parametros, Viaje
from .viajes import desplazar_viaje


def asignar_flota(viajes: list[Viaje], params: Parametros) -> tuple[list[Viaje], list[list[int]]]:
    """Devuelve los viajes (con su hora de salida definitiva) y los viajes de cada camión."""
    resultado = list(viajes)
    orden = sorted(range(len(viajes)), key=lambda k: (viajes[k].salida, viajes[k].holgura_h))
    camiones: list[list[int]] = []
    libre: list[datetime] = []          # cuándo vuelve cada camión a Mataró
    carga = timedelta(hours=params.carga_h)

    for k in orden:
        v = resultado[k]
        elegido = None
        for c, t_libre in enumerate(libre):
            inicio = max(v.salida, t_libre + carga)
            retraso_h = (inicio - v.salida).total_seconds() / 3600
            if retraso_h <= v.holgura_h + 1e-9 and (elegido is None or t_libre > libre[elegido]):
                elegido = c
        if elegido is None:
            camiones.append([k])
            libre.append(v.regreso)
            continue
        inicio = max(v.salida, libre[elegido] + carga)
        if inicio != v.salida:
            v = desplazar_viaje(v, inicio)
            resultado[k] = v
        camiones[elegido].append(k)
        libre[elegido] = v.regreso

    return resultado, camiones
