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


def datos_animacion(esc: Escenario, viaje: Viaje, ruta: dict, carga: dict[int, list[dict]]) -> dict:
    """Diccionario serializable a JSON con todo lo que necesita el componente de simulación."""
    alm = esc.almacen
    puntos = [[alm.lat, alm.lon]] + [[p.pedido.lat, p.pedido.lon] for p in viaje.paradas] + [[alm.lat, alm.lon]]
    km_tramos = [p.km_desde_anterior for p in viaje.paradas]
    km_tramos.append(viaje.km_total - sum(km_tramos))
    ciudades = {p["IdPedido"]: (p["Ciudad"], p["IdPais"]) for p in ruta["Paradas"]}
    return {
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
