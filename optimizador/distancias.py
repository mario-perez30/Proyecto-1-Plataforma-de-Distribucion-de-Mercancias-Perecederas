"""Distancias por carretera estimadas.

Se usa la distancia en línea recta (fórmula de haversine) multiplicada por un
factor de carretera (1,25 por defecto), igual que la función fn_DistanciaKm de
la base de datos.
"""

from __future__ import annotations

import math

RADIO_TIERRA_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta entre dos coordenadas, en km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def matriz_km(puntos: list[tuple[float, float]], factor_carretera: float = 1.25) -> list[list[float]]:
    """Matriz simétrica de km por carretera entre todos los puntos (lat, lon).

    El punto 0 es el almacén; los demás, los pedidos en el orden recibido.
    """
    n = len(puntos)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(*puntos[i], *puntos[j]) * factor_carretera
            m[i][j] = m[j][i] = d
    return m
