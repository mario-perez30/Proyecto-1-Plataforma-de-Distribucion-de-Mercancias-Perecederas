"""Datos para la simulación en tiempo real de un viaje guardado.

Reconstruye los viajes de una planificación de la BD (mismo escenario, mismo
orden de paradas y misma hora de salida) con evaluar_viaje, que es
determinista: así se obtiene la línea de tiempo completa del conductor
(conducción, pausas, descansos, carga y descargas) sin guardarla en la BD.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .datos import cargar_escenario
from .modelo import Escenario, Viaje
from .planificador import matriz_escenario
from .viajes import evaluar_viaje


def _ms(dt: datetime) -> int:
    """Milisegundos epoch tratando las fechas de la BD (sin zona) como UTC."""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def cargar_rutas(conn, id_plan: int) -> tuple[Escenario, list[list[float]], list[dict]]:
    """Escenario, matriz de km y rutas (con conductor, vehículo y paradas) de una planificación."""
    with conn.cursor() as cur:
        cur.execute("SELECT IdEscenario, IdTipoVehiculo FROM Planificaciones WHERE IdPlanificacion = %s", (id_plan,))
        plan = cur.fetchone()
        if plan is None:
            raise ValueError(f"No existe la planificación {id_plan}")
        cur.execute(
            "SELECT r.IdRuta, r.NumCamion, r.NumViaje, r.FechaSalida, r.FechaRegreso, r.KmTotales, r.UnidadesCargadas, "
            "       r.CosteTotal, r.KgCO2, v.Matricula, c.Nombre AS Conductor "
            "FROM Rutas r LEFT JOIN Vehiculos v ON v.IdVehiculo = r.IdVehiculo "
            "LEFT JOIN Conductores c ON c.IdConductor = r.IdConductor "
            "WHERE r.IdPlanificacion = %s ORDER BY r.NumCamion, r.NumViaje", (id_plan,))
        rutas = cur.fetchall()
        cur.execute(
            "SELECT p.IdRuta, p.Orden, p.IdPedido, d.Ciudad, d.IdPais FROM ParadasRuta p "
            "JOIN Rutas r ON r.IdRuta = p.IdRuta JOIN Destinos d ON d.IdDestino = p.IdDestino "
            "WHERE r.IdPlanificacion = %s ORDER BY p.IdRuta, p.Orden", (id_plan,))
        paradas = cur.fetchall()
    for r in rutas:
        r["Paradas"] = [p for p in paradas if p["IdRuta"] == r["IdRuta"]]
    esc = cargar_escenario(conn, plan["IdEscenario"], plan["IdTipoVehiculo"])
    return esc, matriz_escenario(esc), rutas


def viaje_de_ruta(esc: Escenario, km: list[list[float]], ruta: dict) -> Viaje:
    """Vuelve a simular la ruta guardada con su misma hora de salida."""
    indice = {p.id: i for i, p in enumerate(esc.pedidos)}
    secuencia = [indice[p["IdPedido"]] for p in ruta["Paradas"]]
    return evaluar_viaje(secuencia, esc, km, salida=ruta["FechaSalida"])


def carga_de_pedidos(conn, ids: list[int]) -> dict[int, list[dict]]:
    """Unidades por familia de producto y régimen de temperatura de cada pedido."""
    if not ids:
        return {}
    marcas = ", ".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT l.IdPedido, c.Nombre AS Categoria, r.Nombre AS Regimen, SUM(l.Cantidad) AS Unidades, "
            "       COUNT(*) AS Lineas "
            "FROM LineasPedido l JOIN Productos p ON p.IdProducto = l.IdProducto "
            "JOIN Categorias c ON c.IdCategoria = p.IdCategoria JOIN RegimenesTemperatura r ON r.IdRegimen = c.IdRegimen "
            f"WHERE l.IdPedido IN ({marcas}) GROUP BY l.IdPedido, c.Nombre, r.Nombre ORDER BY l.IdPedido, Unidades DESC",
            ids)
        filas = cur.fetchall()
    out: dict[int, list[dict]] = {}
    for f in filas:
        out.setdefault(f["IdPedido"], []).append(
            {"categoria": f["Categoria"], "regimen": f["Regimen"], "unidades": int(f["Unidades"]),
             "lineas": int(f["Lineas"])})
    return out


def trazados_de_viaje(conn, esc: Escenario, viaje: Viaje) -> list[list[list[float]] | None]:
    """Trazado por carretera de cada tramo del viaje (Mataró -> paradas -> Mataró), con caché en la BD."""
    from .carreteras import cargar_trazado
    alm = (esc.almacen.lat, esc.almacen.lon)
    nodos = [(0, alm)] + [(p.pedido.id_destino, (p.pedido.lat, p.pedido.lon)) for p in viaje.paradas] + [(0, alm)]
    return [cargar_trazado(conn, a, b, pa, pb) if a != b else None
            for (a, pa), (b, pb) in zip(nodos, nodos[1:])]


def _tramo_animado(trazado: list[list[float]] | None, a: list[float], b: list[float], horas: float) -> dict:
    """Puntos del tramo con la fracción de tiempo (tf) y de km (kf) en cada punto y la velocidad (v) de cada segmento.

    Las velocidades de OSRM se escalan para que el tramo dure exactamente las horas de la simulación.
    Sin trazado (sin red), línea recta a velocidad media.
    """
    if not trazado or len(trazado) < 2:
        return {"p": [a, b], "tf": [0, 1], "kf": [0, 1], "v": [0.0]}
    tiempos = [(q[2] - p[2]) / q[3] for p, q in zip(trazado, trazado[1:])]
    total_t, total_km = sum(tiempos) or 1.0, trazado[-1][2] or 1.0
    escala = total_t / horas if horas > 0 else 1.0
    tf, acum = [0.0], 0.0
    for t in tiempos:
        acum += t
        tf.append(round(acum / total_t, 5))
    return {"p": [[x[0], x[1]] for x in trazado], "tf": tf,
            "kf": [round(x[2] / total_km, 5) for x in trazado],
            "v": [round(q[3] * escala, 1) for q in trazado[1:]]}


def datos_animacion(esc: Escenario, viaje: Viaje, ruta: dict, carga: dict[int, list[dict]],
                    trazados: list | None = None) -> dict:
    """Diccionario serializable a JSON con todo lo que necesita el componente de simulación."""
    alm = esc.almacen
    puntos = [[alm.lat, alm.lon]] + [[p.pedido.lat, p.pedido.lon] for p in viaje.paradas] + [[alm.lat, alm.lon]]
    km_tramos = [p.km_desde_anterior for p in viaje.paradas]
    km_tramos.append(viaje.km_total - sum(km_tramos))
    ciudades = {p["IdPedido"]: (p["Ciudad"], p["IdPais"]) for p in ruta["Paradas"]}
    horas_tramo = [0.0] * len(km_tramos)
    for e in viaje.eventos:
        if e["tipo"] == "conduccion":
            horas_tramo[e["tramo"]] += (e["fin"] - e["inicio"]).total_seconds() / 3600
    trazados = trazados or [None] * len(km_tramos)
    tramos = []
    for i, h in enumerate(horas_tramo):
        t = _tramo_animado(trazados[i], puntos[i], puntos[i + 1], h)
        if t["v"] == [0.0]:
            t["v"] = [round(km_tramos[i] / h, 1) if h > 0 else 0.0]
        tramos.append(t)
    return {
        "tramos": tramos,
        "carretera": any(trazados),
        "almacen": {"lat": alm.lat, "lon": alm.lon, "nombre": "Mataró"},
        "puntos": puntos,
        "km_tramos": km_tramos,
        "paradas": [{
            "orden": n, "pedido": p.pedido.id, "ciudad": ciudades.get(p.pedido.id, ("", ""))[0],
            "pais": ciudades.get(p.pedido.id, ("", ""))[1], "unidades": p.pedido.unidades,
            "llegada": _ms(p.llegada), "salida": _ms(p.salida), "limite": _ms(p.pedido.limite),
            "caducidad": _ms(p.pedido.caducidad), "carga": carga.get(p.pedido.id, []),
        } for n, p in enumerate(viaje.paradas, start=1)],
        "eventos": [{"tipo": e["tipo"], "inicio": _ms(e["inicio"]), "fin": _ms(e["fin"]),
                     "tramo": e["tramo"], "f0": e["f0"], "f1": e["f1"]} for e in viaje.eventos],
        "conductor": ruta.get("Conductor") or "Sin asignar",
        "matricula": ruta.get("Matricula") or "—",
        "camion": ruta["NumCamion"], "viaje": ruta["NumViaje"],
        "tipo": esc.tipo.nombre, "capacidad": esc.tipo.capacidad, "velocidad": esc.tipo.velocidad_kmh,
        "unidades": viaje.unidades, "km_total": viaje.km_total, "coste": viaje.coste_total,
        "co2": viaje.kg_co2, "inicio": _ms(viaje.eventos[0]["inicio"]), "fin": _ms(viaje.regreso),
        "params": {"max_diaria": esc.params.conduccion_max_diaria_h, "continua": esc.params.conduccion_continua_max_h},
    }
