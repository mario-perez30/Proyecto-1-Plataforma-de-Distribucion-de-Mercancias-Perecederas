"""Pruebas unitarias del optimizador con un escenario sintético (sin base de datos)."""

from datetime import datetime, timedelta

import pytest

from optimizador.distancias import haversine_km
from optimizador.flota import asignar_flota
from optimizador.heuristica import clarke_wright
from optimizador.modelo import Almacen, Escenario, Parametros, Pedido, TarifaExterna, TipoVehiculo
from optimizador.planificador import matriz_escenario, planificar
from optimizador.tiempos import RelojConductor
from optimizador.viajes import evaluar_viaje

LISTO = datetime(2026, 12, 4, 6, 0)
CIUDADES = {  # (lat, lon, unidades)
    "Zaragoza": (41.6488, -0.8891, 5000),
    "Valencia": (39.4699, -0.3763, 6000),
    "Madrid": (40.4168, -3.7038, 7000),
    "Bilbao": (43.2630, -2.9350, 4500),
    "Sevilla": (37.3891, -5.9845, 8000),
    "Lisboa": (38.7223, -9.1393, 6500),
}


@pytest.fixture
def escenario() -> Escenario:
    tipo = TipoVehiculo(id=1, nombre="12 t", capacidad=12000, velocidad_kmh=70, litros_km=0.27, kg_co2_km=0.72,
                        coste_combustible_km=0.37, coste_peaje_km=0.04, coste_mantenimiento_km=0.12,
                        coste_fijo_km=0.15, precio_adquisicion=95000)
    pedidos = [Pedido(id=k + 1, id_destino=k + 1, lat=lat, lon=lon, unidades=u, listo=LISTO,
                      limite=LISTO + timedelta(days=6), caducidad=LISTO + timedelta(days=7))
               for k, (lat, lon, u) in enumerate(CIUDADES.values())]
    return Escenario(id=1, almacen=Almacen(1, "Mataró", 41.5381, 2.4445), pedidos=pedidos, tipo=tipo,
                     params=Parametros(), tarifa=TarifaExterna(120, 1.85, 0))


def test_haversine_madrid_barcelona():
    assert haversine_km(40.4168, -3.7038, 41.3874, 2.1686) == pytest.approx(505, abs=5)


def test_reloj_aplica_pausa_y_descanso_diario():
    reloj = RelojConductor(LISTO, Parametros())
    reloj.conducir(10)
    # 4,5 h + pausa 0,75 h + 4,5 h + descanso 11 h + 1 h
    assert reloj.t - LISTO == timedelta(hours=21.75)
    assert reloj.descansos_diarios == 1
    assert reloj.horas_conduccion == pytest.approx(10)


def test_viaje_individual_ida_y_vuelta(escenario):
    km = matriz_escenario(escenario)
    v = evaluar_viaje([0], escenario, km)
    assert v.factible
    assert v.km_total == pytest.approx(2 * km[0][1])
    assert v.coste_total > 0 and v.kg_co2 > 0


def test_viaje_que_supera_capacidad_no_es_factible(escenario):
    km = matriz_escenario(escenario)
    assert not evaluar_viaje([2, 4], escenario, km).factible   # 7000 + 8000 > 12000


def test_plazo_incumplido_no_es_factible(escenario):
    esc = escenario
    esc.pedidos[5] = Pedido(**{**esc.pedidos[5].__dict__, "limite": LISTO + timedelta(hours=5)})
    assert not evaluar_viaje([5], esc, matriz_escenario(esc)).factible


def _comprobar_rutas(rutas, esc):
    visitados = sorted(i for r in rutas for i in r)
    assert visitados == list(range(len(esc.pedidos))), "cada pedido en un solo viaje"
    for r in rutas:
        assert sum(esc.pedidos[i].unidades for i in r) <= esc.tipo.capacidad


def test_clarke_wright_cubre_todo_y_respeta_capacidad(escenario):
    rutas = clarke_wright(escenario, matriz_escenario(escenario))
    _comprobar_rutas(rutas, escenario)
    assert len(rutas) < len(escenario.pedidos), "debe consolidar algún viaje"


def test_ortools_cubre_todo_y_respeta_capacidad(escenario):
    from optimizador.ortools_vrp import resolver_ortools
    rutas = resolver_ortools(escenario, matriz_escenario(escenario), segundos=2)
    _comprobar_rutas(rutas, escenario)


def test_flota_reutiliza_camion_cuando_hay_tiempo(escenario):
    km = matriz_escenario(escenario)
    viajes = [evaluar_viaje([0], escenario, km), evaluar_viaje([1], escenario, km)]
    viajes, camiones = asignar_flota(viajes, escenario.params)
    assert len(camiones) == 1, "Zaragoza y Valencia caben en un camión en 6 días"
    assert viajes[camiones[0][1]].salida >= viajes[camiones[0][0]].regreso


def test_eventos_cubren_todo_el_viaje_sin_huecos(escenario):
    v = evaluar_viaje([5], escenario, matriz_escenario(escenario))      # Lisboa: viaje largo
    tipos = [e["tipo"] for e in v.eventos]
    assert tipos[0] == "carga" and "descarga" in tipos
    assert "pausa" in tipos and "descanso" in tipos, "un viaje de más de 9 h necesita pausas y descanso"
    for a, b in zip(v.eventos, v.eventos[1:]):
        assert a["fin"] == b["inicio"], "los eventos deben ser contiguos"
    assert v.eventos[-1]["fin"] == v.regreso
    horas = sum((e["fin"] - e["inicio"]).total_seconds() for e in v.eventos if e["tipo"] == "conduccion") / 3600
    assert horas == pytest.approx(v.horas_conduccion)


def test_desplazar_viaje_mueve_tambien_los_eventos(escenario):
    from optimizador.viajes import desplazar_viaje
    v = evaluar_viaje([0], escenario, matriz_escenario(escenario))
    v2 = desplazar_viaje(v, v.salida + timedelta(hours=3))
    assert v2.eventos[0]["inicio"] - v.eventos[0]["inicio"] == timedelta(hours=3)
    assert v2.regreso - v.regreso == timedelta(hours=3)


def test_conductor_descansa_entre_viajes(escenario):
    from optimizador.persistencia import asignar_conductores
    sol = planificar(escenario, "directo")
    asignacion = asignar_conductores(sol, [1, 2, 3, 4, 5, 6, 7, 8], escenario.params.descanso_diario_h)
    por_conductor: dict = {}
    for k, c in asignacion.items():
        por_conductor.setdefault(c, []).append(sol.viajes[k])
    for viajes in por_conductor.values():
        viajes.sort(key=lambda v: v.salida)
        for a, b in zip(viajes, viajes[1:]):
            assert (b.salida - a.regreso).total_seconds() / 3600 >= escenario.params.descanso_diario_h


def test_carretera_real_usa_sus_km_y_tiempos(escenario):
    from dataclasses import replace
    puntos = [0] + [p.id_destino for p in escenario.pedidos]
    carretera = {(a, b): (100.0 + a + b, 2.0) for a in puntos for b in puntos if a != b}
    esc = replace(escenario, carretera=carretera)
    km = matriz_escenario(esc)
    assert km[0][1] == pytest.approx(101.0) and esc.horas[0][1] == pytest.approx(2.0)
    v = evaluar_viaje([0], esc, km)
    assert v.horas_conduccion == pytest.approx(4.0), "2 h de ida + 2 h de vuelta, sin usar la velocidad media"


def test_velocidad_camion_limitada_y_tramo_animado():
    from optimizador.carreteras import velocidad_camion
    from optimizador.simulacion import _tramo_animado
    assert velocidad_camion(130) == 90 and velocidad_camion(50) == pytest.approx(44)
    trazado = [[41.0, 2.0, 0.0, 0.0], [41.1, 2.0, 9.0, 90.0], [41.2, 2.0, 10.0, 30.0]]
    t = _tramo_animado(trazado, [41.0, 2.0], [41.2, 2.0], horas=0.2)
    assert t["tf"][0] == 0 and t["tf"][-1] == pytest.approx(1)
    assert t["tf"][1] == pytest.approx(0.75), "9 km a 90 km/h = 0,1 h de 0,1333 h"
    assert t["v"][0] > t["v"][1], "la autovía es más rápida que el tramo urbano"


@pytest.mark.parametrize("algoritmo", ["directo", "clarke-wright", "ortools"])
def test_planificar_sin_pedidos_fuera_de_plazo(escenario, algoritmo):
    sol = planificar(escenario, algoritmo, segundos=2)
    assert sol.pedidos_fuera_plazo == 0
    assert sum(len(v.paradas) for v in sol.viajes) == len(escenario.pedidos)
    assert sol.num_camiones <= len(sol.viajes)
    assert sol.coste_externalizado > 0
