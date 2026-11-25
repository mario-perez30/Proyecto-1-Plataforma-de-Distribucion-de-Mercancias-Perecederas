"""Evaluación de un viaje: horarios, cumplimiento de plazos, km, costes y CO2.

La misma lógica de costes que la vista vw_EstimacionEnvioDirecto de la BD:
coste por km (combustible, peajes, mantenimiento, amortización), horas del
conductor, dietas y pernoctas.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .modelo import Escenario, Parada, Pedido, Viaje
from .tiempos import RelojConductor


def evaluar_viaje(secuencia: list[int], esc: Escenario, km: list[list[float]],
                  salida: datetime | None = None) -> Viaje:
    """Simula un viaje que sale de Mataró, entrega los pedidos en el orden dado y vuelve.

    secuencia: índices de esc.pedidos (0..n-1) en orden de entrega.
    km:        matriz de km con el almacén en la posición 0 y el pedido i en la i+1.
    salida:    hora de salida tras la carga; por defecto, el momento en que todos
               los pedidos están listos más el tiempo de carga.
    """
    pedidos: list[Pedido] = [esc.pedidos[i] for i in secuencia]
    tipo, p = esc.tipo, esc.params
    if salida is None:
        salida = max(x.listo for x in pedidos) + timedelta(hours=p.carga_h)

    reloj = RelojConductor(salida - timedelta(hours=p.carga_h), p)
    reloj.trabajar(p.carga_h, "carga")

    paradas: list[Parada] = []
    km_total = 0.0
    nodo_ant = 0
    factible, motivo = True, ""
    unidades = sum(x.unidades for x in pedidos)
    if unidades > tipo.capacidad:
        factible, motivo = False, f"capacidad superada ({unidades} > {tipo.capacidad})"

    for tramo, (i, ped) in enumerate(zip(secuencia, pedidos)):
        d = km[nodo_ant][i + 1]
        reloj.tramo = tramo
        reloj.conducir(d / tipo.velocidad_kmh)
        llegada = reloj.t
        reloj.trabajar(ped.descarga_h, "descarga")
        paradas.append(Parada(pedido=ped, km_desde_anterior=d, llegada=llegada, salida=reloj.t))
        km_total += d
        nodo_ant = i + 1
        if llegada > ped.limite and factible:
            factible, motivo = False, f"pedido {ped.id} llega después de su límite"

    d = km[nodo_ant][0]
    reloj.tramo = len(pedidos)
    reloj.conducir(d / tipo.velocidad_kmh)
    km_total += d

    pernoctas = reloj.descansos_diarios
    return Viaje(
        paradas=paradas,
        salida=salida,
        regreso=reloj.t,
        km_total=km_total,
        horas_conduccion=reloj.horas_conduccion,
        horas_trabajo=reloj.horas_trabajo,
        pernoctas=pernoctas,
        unidades=unidades,
        litros=km_total * tipo.litros_km,
        kg_co2=km_total * tipo.kg_co2_km,
        coste_combustible=km_total * tipo.coste_combustible_km,
        coste_peajes=km_total * tipo.coste_peaje_km,
        coste_mantenimiento=km_total * tipo.coste_mantenimiento_km,
        coste_fijo=km_total * tipo.coste_fijo_km,
        coste_conductor=reloj.horas_trabajo * p.coste_conductor_h,
        coste_dietas=(pernoctas + 1) * p.dieta_dia + pernoctas * p.pernocta,
        factible=factible,
        motivo=motivo,
        eventos=reloj.eventos,
    )


def desplazar_viaje(v: Viaje, nueva_salida: datetime) -> Viaje:
    """Mismo viaje con todas sus horas desplazadas (el camión sale más tarde)."""
    delta = nueva_salida - v.salida
    paradas = [Parada(x.pedido, x.km_desde_anterior, x.llegada + delta, x.salida + delta) for x in v.paradas]
    fuera = [x.pedido.id for x in paradas if x.llegada > x.pedido.limite]
    eventos = [{**e, "inicio": e["inicio"] + delta, "fin": e["fin"] + delta} for e in v.eventos]
    return Viaje(**{**v.__dict__, "paradas": paradas, "salida": v.salida + delta, "regreso": v.regreso + delta,
                    "eventos": eventos,
                    "factible": v.factible and not fuera,
                    "motivo": v.motivo or (f"pedido {fuera[0]} llega después de su límite" if fuera else "")})


def coste_externalizado(esc: Escenario, km: list[list[float]]) -> float:
    """Coste de enviar cada pedido con el operador externo (fijo + km de ida + unidades)."""
    if esc.tarifa is None:
        return 0.0
    t = esc.tarifa
    return sum(t.fijo_envio + km[0][i + 1] * t.coste_km + ped.unidades * t.coste_unidad
               for i, ped in enumerate(esc.pedidos))
