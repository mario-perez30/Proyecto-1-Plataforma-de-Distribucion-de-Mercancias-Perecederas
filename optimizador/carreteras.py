"""Rutas por carretera real con OSRM (Open Source Routing Machine) sobre OpenStreetMap.

* Matriz de km y tiempos entre Mataró y los destinos con pedidos (API "table").
  Se calcula una vez y se guarda en database/07_matriz_carretera.sql:
      python -m optimizador.carreteras --sql database/07_matriz_carretera.sql
* Trazado de cada tramo con la velocidad de cada segmento (API "route"),
  bajo demanda y en caché en la tabla GeometriaTramos.

Velocidad del camión en un segmento (o en un tramo completo):
    v_camion = min(VelocidadMaxCamionKmh, FactorVelocidadCamion x v_coche)
así el camión va a 90 km/h por autovía y más despacio por nacionales y ciudad.

Se usa el servidor público de demostración de OSRM con pocas peticiones y
pausas entre ellas. Datos de rutas (c) colaboradores de OpenStreetMap (ODbL).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

OSRM = "https://router.project-osrm.org"
AGENTE = "BDIADelivery-prototipo-academico/0.1"
BLOQUE = 40           # puntos por bloque en la API table (el servidor limita a 100)
PAUSA_S = 1.0         # pausa entre peticiones al servidor público
ALMACEN = 0           # identificador del almacén principal en las tablas de carreteras


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = json.load(r)
    if datos.get("code") != "Ok":
        raise RuntimeError(f"OSRM respondió {datos.get('code')}: {datos.get('message', '')}")
    return datos


def _coords(puntos: list[tuple[float, float]]) -> str:
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in puntos)


def velocidad_camion(v_coche_kmh: float, v_max: float = 90.0, factor: float = 0.88) -> float:
    """Velocidad del camión en un tramo a partir de la de un turismo."""
    return max(5.0, min(v_max, factor * v_coche_kmh))


def minutos_camion(km: float, minutos_coche: float, v_max: float = 90.0, factor: float = 0.88) -> float:
    """Tiempo del camión para un tramo completo (con su velocidad media de turismo)."""
    if km <= 0 or minutos_coche <= 0:
        return 0.0
    return 60 * km / velocidad_camion(km / (minutos_coche / 60), v_max, factor)


def calcular_matriz(puntos: dict[int, tuple[float, float]], v_max: float = 90.0,
                    factor: float = 0.88) -> dict[tuple[int, int], tuple[float, float, float]]:
    """Km, minutos de coche y minutos de camión entre todos los pares de puntos.

    puntos: {id: (lat, lon)} con id 0 = almacén e IdDestino para los destinos.
    """
    ids = list(puntos)
    bloques = [ids[i:i + BLOQUE] for i in range(0, len(ids), BLOQUE)]
    matriz: dict[tuple[int, int], tuple[float, float, float]] = {}
    for a in bloques:
        for b in bloques:
            todos = a + [x for x in b if x not in a]
            src = ";".join(str(todos.index(x)) for x in a)
            dst = ";".join(str(todos.index(x)) for x in b)
            url = (f"{OSRM}/table/v1/driving/{_coords([puntos[x] for x in todos])}"
                   f"?sources={src}&destinations={dst}&annotations=distance,duration")
            r = _get(url)
            for i, pa in enumerate(a):
                for j, pb in enumerate(b):
                    km = (r["distances"][i][j] or 0) / 1000
                    mc = (r["durations"][i][j] or 0) / 60
                    matriz[(pa, pb)] = (km, mc, minutos_camion(km, mc, v_max, factor))
            time.sleep(PAUSA_S)
    return matriz


def trazado(origen: tuple[float, float], destino: tuple[float, float], v_max: float = 90.0,
            factor: float = 0.88, km_min_segmento: float = 0.4) -> tuple[list[list[float]], float, float]:
    """Trazado por carretera entre dos puntos.

    Devuelve ([[lat, lon, km_acumulado, km/h del camión], ...], km, minutos de camión).
    Los segmentos de OSRM se agrupan hasta km_min_segmento para aligerar el dibujo.
    """
    url = (f"{OSRM}/route/v1/driving/{_coords([origen, destino])}"
           f"?overview=full&geometries=geojson&annotations=distance,duration")
    r = _get(url)["routes"][0]
    coords = r["geometry"]["coordinates"]
    ann = r["legs"][0]["annotation"]
    puntos = [[coords[0][1], coords[0][0], 0.0, 0.0]]
    km_acum, minutos, d_bloque, t_bloque = 0.0, 0.0, 0.0, 0.0
    for k, (d, t) in enumerate(zip(ann["distance"], ann["duration"])):
        d_bloque += d / 1000
        t_bloque += t / 3600
        ultimo = k == len(ann["distance"]) - 1
        if d_bloque >= km_min_segmento or ultimo:
            v = velocidad_camion(d_bloque / t_bloque if t_bloque > 0 else v_max, v_max, factor)
            km_acum += d_bloque
            minutos += 60 * d_bloque / v
            lon, lat = coords[k + 1]
            puntos.append([round(lat, 5), round(lon, 5), round(km_acum, 3), round(v, 1)])
            d_bloque = t_bloque = 0.0
    return puntos, km_acum, minutos


def cargar_trazado(conn, a: int, b: int, pa: tuple[float, float], pb: tuple[float, float],
                   v_max: float = 90.0, factor: float = 0.88) -> list[list[float]] | None:
    """Trazado del tramo a -> b desde la caché GeometriaTramos o, si no está, desde OSRM.

    Devuelve None si no hay conexión con OSRM (la simulación usa entonces la línea recta).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT Puntos FROM GeometriaTramos WHERE PuntoOrigen = %s AND PuntoDestino = %s", (a, b))
        fila = cur.fetchone()
        if fila:
            return json.loads(fila["Puntos"])
        try:
            puntos, km, minutos = trazado(pa, pb, v_max, factor)
        except Exception:  # noqa: BLE001 - sin red: se dibuja en línea recta
            return None
        cur.execute("INSERT INTO GeometriaTramos (PuntoOrigen, PuntoDestino, Km, MinutosCamion, Puntos) "
                    "VALUES (%s, %s, %s, %s, %s)", (a, b, round(km, 3), round(minutos, 2), json.dumps(puntos)))
    conn.commit()
    return puntos


def tramos_de_punto(nuevo: int, puntos: dict[int, tuple[float, float]], v_max: float = 90.0,
                    factor: float = 0.88) -> list[tuple[int, int, float, float, float]]:
    """Tramos entre un punto nuevo y todos los demás, en los dos sentidos (para un destino nuevo)."""
    otros = [p for p in puntos if p != nuevo]
    filas = []
    for i in range(0, len(otros), 80):
        bloque = otros[i:i + 80]
        coords = _coords([puntos[nuevo]] + [puntos[x] for x in bloque])
        resto = ";".join(str(k) for k in range(1, len(bloque) + 1))
        for ida in (True, False):
            src, dst = ("0", resto) if ida else (resto, "0")
            r = _get(f"{OSRM}/table/v1/driving/{coords}?sources={src}&destinations={dst}&annotations=distance,duration")
            for k, x in enumerate(bloque):
                d = r["distances"][0][k] if ida else r["distances"][k][0]
                t = r["durations"][0][k] if ida else r["durations"][k][0]
                km, mc = (d or 0) / 1000, (t or 0) / 60
                a, b = (nuevo, x) if ida else (x, nuevo)
                filas.append((a, b, round(km, 3), round(mc, 2), round(minutos_camion(km, mc, v_max, factor), 2)))
            time.sleep(PAUSA_S)
    return filas


def puntos_con_pedidos(conn) -> dict[int, tuple[float, float]]:
    """Almacén principal (0) y destinos que tienen algún pedido."""
    with conn.cursor() as cur:
        cur.execute("SELECT Latitud, Longitud FROM Almacenes WHERE EsPrincipal = 1")
        a = cur.fetchone()
        puntos = {ALMACEN: (float(a["Latitud"]), float(a["Longitud"]))}
        cur.execute("SELECT DISTINCT d.IdDestino, d.Latitud, d.Longitud FROM Destinos d "
                    "JOIN Pedidos p ON p.IdDestino = d.IdDestino ORDER BY d.IdDestino")
        for f in cur.fetchall():
            puntos[f["IdDestino"]] = (float(f["Latitud"]), float(f["Longitud"]))
    return puntos


def escribir_sql(matriz: dict[tuple[int, int], tuple[float, float, float]], ruta: str) -> None:
    filas = [f"({a}, {b}, {km:.3f}, {mc:.2f}, {mt:.2f})" for (a, b), (km, mc, mt) in sorted(matriz.items())]
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- =====================================================================\n"
                "-- BDIADelivery - MATRIZ DE KM Y TIEMPOS POR CARRETERA (generado)\n"
                "-- python -m optimizador.carreteras --sql database/07_matriz_carretera.sql\n"
                "-- Fuente: OSRM sobre OpenStreetMap (c) colaboradores de OpenStreetMap (ODbL)\n"
                "-- Punto 0 = Mataró; resto = IdDestino. Ejecutar después de 06.\n"
                "-- =====================================================================\n\n"
                "USE `BDIADelivery`;\nSET NAMES utf8mb4;\n\n")
        for i in range(0, len(filas), 1000):
            f.write("INSERT INTO `TramosCarretera` (`PuntoOrigen`, `PuntoDestino`, `Km`, `MinutosCoche`, "
                    "`MinutosCamion`) VALUES\n" + ",\n".join(filas[i:i + 1000]) + ";\n")
        f.write("\nSELECT COUNT(*) AS Tramos FROM `TramosCarretera`;\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m optimizador.carreteras",
                                 description="Calcula la matriz de km y tiempos por carretera con OSRM.")
    ap.add_argument("--sql", required=True, help="Archivo SQL de salida (database/07_matriz_carretera.sql)")
    args = ap.parse_args(argv)
    from .datos import conectar
    conn = conectar()
    try:
        puntos = puntos_con_pedidos(conn)
    finally:
        conn.close()
    print(f"Calculando {len(puntos)} x {len(puntos)} tramos por carretera con OSRM…")
    matriz = calcular_matriz(puntos)
    escribir_sql(matriz, args.sql)
    sin_ruta = sum(1 for (a, b), (km, _, _) in matriz.items() if a != b and km == 0)
    print(f"{len(matriz)} tramos escritos en {args.sql} ({sin_ruta} sin ruta)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
