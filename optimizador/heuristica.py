"""Algoritmo de ahorros de Clarke-Wright (1964).

Heurística constructiva clásica para rutas de vehículos:
    1. Empieza con un viaje por pedido (Mataró -> pedido -> Mataró).
    2. Calcula el ahorro de unir cada par de pedidos i, j en el mismo viaje:
           ahorro(i, j) = d(0, i) + d(0, j) - d(i, j)
    3. Recorre los ahorros de mayor a menor y une los dos viajes si i y j están
       en un extremo de su viaje, no se supera la capacidad y todos los pedidos
       siguen llegando antes de su límite.

Sirve como línea base para comparar con OR-Tools.
"""

from __future__ import annotations

from .modelo import Escenario
from .viajes import evaluar_viaje


def clarke_wright(esc: Escenario, km: list[list[float]]) -> list[list[int]]:
    """Devuelve las secuencias de pedidos (índices de esc.pedidos) de cada viaje."""
    n = len(esc.pedidos)
    capacidad = esc.tipo.capacidad
    rutas: dict[int, list[int]] = {i: [i] for i in range(n)}
    ruta_de: dict[int, int] = {i: i for i in range(n)}
    carga: dict[int, int] = {i: esc.pedidos[i].unidades for i in range(n)}

    ahorros = sorted(
        ((km[0][i + 1] + km[0][j + 1] - km[i + 1][j + 1], i, j) for i in range(n) for j in range(i + 1, n)),
        reverse=True,
    )

    for ahorro, i, j in ahorros:
        if ahorro <= 0:
            break
        ri, rj = ruta_de[i], ruta_de[j]
        if ri == rj or carga[ri] + carga[rj] > capacidad:
            continue
        a, b = rutas[ri], rutas[rj]
        # i y j tienen que quedar contiguos: se prueban las cuatro orientaciones posibles
        candidatas = []
        if a[-1] == i and b[0] == j:
            candidatas.append(a + b)
        if a[0] == i and b[-1] == j:
            candidatas.append(b + a)
        if a[-1] == i and b[-1] == j:
            candidatas.append(a + b[::-1])
        if a[0] == i and b[0] == j:
            candidatas.append(a[::-1] + b)
        for nueva in candidatas:
            if evaluar_viaje(nueva, esc, km).factible:
                rutas[ri] = nueva
                carga[ri] += carga.pop(rj)
                del rutas[rj]
                for k in b:
                    ruta_de[k] = ri
                break

    return list(rutas.values())
