"""Interfaz del prototipo: planificador de rutas de IA DELIVERY SL.

Ejecutar con:  .venv/Scripts/streamlit run app.py

Pestañas:
    Planificar      Elige escenario, camión y algoritmo; calcula, guarda y muestra las rutas.
    Planificaciones Compara las planificaciones guardadas y muestra el mapa de cualquiera.
    Pedidos         Pedidos del escenario con sus fechas de fabricación y caducidad.
    Parámetros      Costes, normativa y precios que usa el optimizador.
"""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from optimizador.datos import cargar_escenario, conectar, listar_escenarios, listar_tipos_vehiculo
from optimizador.persistencia import guardar_solucion
from optimizador.planificador import planificar

st.set_page_config(page_title="IA DELIVERY · Planificador de rutas", layout="wide")

ALGORITMOS = {"OR-Tools": "ortools", "Clarke-Wright": "clarke-wright", "Envío directo (un camión por pedido)": "directo"}
PALETA = [(31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40), (148, 103, 189), (140, 86, 75),
          (227, 119, 194), (127, 127, 127), (188, 189, 34), (23, 190, 207)]


def consulta(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall())
    finally:
        conn.close()


def euros(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def capas_mapa(rutas: pd.DataFrame, almacen: tuple[float, float]) -> list[pdk.Layer]:
    """Capas de pydeck: una línea por viaje (color por camión) y un punto por destino.

    rutas: columnas NumCamion, NumViaje, Orden, Lat, Lon, Destino, IdPedido.
    """
    caminos, puntos = [], []
    for (camion, viaje), g in rutas.sort_values("Orden").groupby(["NumCamion", "NumViaje"]):
        color = PALETA[(int(camion) - 1) % len(PALETA)]
        coords = [[almacen[1], almacen[0]]] + g[["Lon", "Lat"]].values.tolist() + [[almacen[1], almacen[0]]]
        caminos.append({"path": coords, "color": color, "nombre": f"Camión {camion} · viaje {viaje} · {len(g)} paradas"})
        for _, r in g.iterrows():
            puntos.append({"lon": r["Lon"], "lat": r["Lat"], "color": color,
                           "nombre": f"Pedido {r['IdPedido']} · {r['Destino']} · camión {camion}"})
    return [
        pdk.Layer("PathLayer", caminos, get_path="path", get_color="color", width_min_pixels=2,
                  pickable=True, get_width=3),
        pdk.Layer("ScatterplotLayer", puntos, get_position=["lon", "lat"], get_fill_color="color",
                  get_radius=6000, pickable=True),
        pdk.Layer("ScatterplotLayer", [{"lon": almacen[1], "lat": almacen[0], "nombre": "Mataró (almacén)"}],
                  get_position=["lon", "lat"], get_fill_color=[0, 0, 0], get_radius=14000, pickable=True),
    ]


def mostrar_mapa(rutas: pd.DataFrame, almacen: tuple[float, float]) -> None:
    vista = pdk.ViewState(latitude=40.2, longitude=-3.5, zoom=5)
    st.pydeck_chart(pdk.Deck(layers=capas_mapa(rutas, almacen), initial_view_state=vista,
                             tooltip={"text": "{nombre}"}), use_container_width=True)


def rutas_de_plan(id_plan: int) -> pd.DataFrame:
    return consulta(
        "SELECT r.NumCamion, r.NumViaje, p.Orden, p.IdPedido, d.Ciudad AS Destino, "
        "       CAST(d.Latitud AS DOUBLE) AS Lat, CAST(d.Longitud AS DOUBLE) AS Lon "
        "FROM Rutas r JOIN ParadasRuta p ON p.IdRuta = r.IdRuta JOIN Destinos d ON d.IdDestino = p.IdDestino "
        "WHERE r.IdPlanificacion = %s", (id_plan,))


def almacen_principal() -> tuple[float, float]:
    a = consulta("SELECT Latitud, Longitud FROM Almacenes WHERE EsPrincipal = 1").iloc[0]
    return float(a["Latitud"]), float(a["Longitud"])


# ---------------------------------------------------------------------------
st.title("Planificador de rutas · IA DELIVERY SL")
st.caption("Reparto de mercancías perecederas desde Mataró a España, Portugal y Andorra.")

try:
    conn = conectar()
except Exception as e:  # noqa: BLE001 - se muestra cualquier fallo de conexión al usuario
    st.error(f"No se puede conectar con la base de datos BDIADelivery: {e}")
    st.info("Arranca MySQL en XAMPP o configura BDIA_HOST, BDIA_USER y BDIA_PASSWORD.")
    st.stop()
with conn.cursor() as cur:
    escenarios = listar_escenarios(cur)
    tipos = listar_tipos_vehiculo(cur)
conn.close()

tab_plan, tab_hist, tab_ped, tab_par = st.tabs(["Planificar", "Planificaciones", "Pedidos", "Parámetros"])

# --- Planificar -------------------------------------------------------------
with tab_plan:
    c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
    esc_sel = c1.selectbox("Escenario", escenarios, format_func=lambda e: f"{e['Nombre']} ({e['Pedidos']} pedidos)")
    tipo_sel = c2.selectbox("Camión (flota homogénea)", tipos,
                            format_func=lambda t: f"{t['TipoVehiculo']} · {t['CapacidadUnidades']:,} uds".replace(",", "."))
    alg_nombre = c3.selectbox("Algoritmo", list(ALGORITMOS))
    segundos = c4.number_input("Segundos", 5, 300, 30, help="Tiempo máximo de búsqueda de OR-Tools")
    guardar = st.checkbox("Guardar la planificación en la base de datos", value=True)

    if st.button("Calcular rutas", type="primary"):
        with st.spinner("Calculando rutas y flota mínima…"):
            conn = conectar()
            try:
                esc = cargar_escenario(conn, esc_sel["IdEscenario"], tipo_sel["IdTipoVehiculo"])
                sol = planificar(esc, ALGORITMOS[alg_nombre], segundos=int(segundos))
                id_plan = guardar_solucion(conn, esc, sol) if guardar else None
            finally:
                conn.close()
        st.session_state["ultima"] = (esc, sol, id_plan)

    if "ultima" in st.session_state:
        esc, sol, id_plan = st.session_state["ultima"]
        ahorro = sol.coste_externalizado - sol.coste_total
        k = st.columns(3) + st.columns(3)
        k[0].metric("Camiones necesarios", sol.num_camiones)
        k[1].metric("Viajes", len(sol.viajes))
        k[2].metric("Km totales", f"{sol.km_total:,.0f}".replace(",", "."))
        k[3].metric("Coste flota propia", euros(sol.coste_total))
        k[4].metric("Frente a externalizar", euros(ahorro), delta="ahorro" if ahorro > 0 else "sobrecoste",
                    delta_color="normal" if ahorro > 0 else "inverse")
        k[5].metric("CO2", f"{sol.kg_co2 / 1000:.1f} t")
        st.caption(f"{sol.algoritmo} · {esc.tipo.nombre} · {sol.pedidos_fuera_plazo} pedidos fuera de plazo · "
                   f"calculado en {sol.tiempo_calculo_s:.1f} s"
                   + (f" · guardado como planificación {id_plan}" if id_plan else ""))

        filas = []
        for c, indices in enumerate(sol.camiones, start=1):
            for nv, idx in enumerate(indices, start=1):
                v = sol.viajes[idx]
                for orden, p in enumerate(v.paradas, start=1):
                    filas.append({"NumCamion": c, "NumViaje": nv, "Orden": orden, "IdPedido": p.pedido.id,
                                  "Destino": f"destino {p.pedido.id_destino}", "Lat": p.pedido.lat, "Lon": p.pedido.lon})
        mostrar_mapa(pd.DataFrame(filas), (esc.almacen.lat, esc.almacen.lon))

        tabla = pd.DataFrame([{
            "Camión": c, "Viaje": nv, "Pedidos": ", ".join(map(str, v.ids_pedidos)), "Unidades": v.unidades,
            "Ocupación %": round(100 * v.unidades / esc.tipo.capacidad, 1), "Salida": v.salida, "Regreso": v.regreso,
            "Km": round(v.km_total), "Coste €": round(v.coste_total, 2), "Holgura h": round(v.holgura_h, 1),
        } for c, indices in enumerate(sol.camiones, start=1) for nv, v in
            ((nv, sol.viajes[i]) for nv, i in enumerate(indices, start=1))])
        st.dataframe(tabla, use_container_width=True, hide_index=True)

# --- Planificaciones guardadas ---------------------------------------------
with tab_hist:
    res = consulta("SELECT IdPlanificacion AS Plan, Algoritmo, TipoVehiculo AS Camion, NumCamiones, NumRutas AS Viajes, "
                   "ROUND(KmTotales) AS Km, CosteTotal, ROUND(KgCO2 / 1000, 1) AS `CO2 t`, OcupacionMediaPct, "
                   "PedidosPlanificados, PedidosFueraDePlazo, TiempoCalculoSeg, FechaEjecucion "
                   "FROM vw_ResumenPlanificacion ORDER BY IdPlanificacion DESC")
    if res.empty:
        st.info("Todavía no hay planificaciones guardadas.")
    else:
        st.dataframe(res, use_container_width=True, hide_index=True)
        graf = res.assign(Etiqueta=res["Plan"].astype(str) + " · " + res["Algoritmo"])
        g1, g2 = st.columns(2)
        g1.bar_chart(graf.set_index("Etiqueta")["CosteTotal"].astype(float), y_label="Coste (€)")
        g2.bar_chart(graf.set_index("Etiqueta")["NumCamiones"], y_label="Camiones")
        plan = st.selectbox("Ver en el mapa la planificación", res["Plan"].tolist())
        mostrar_mapa(rutas_de_plan(int(plan)), almacen_principal())

# --- Pedidos -----------------------------------------------------------------
with tab_ped:
    ped = consulta("SELECT p.IdPedido, p.IdEscenario, c.Nombre AS Cliente, d.Ciudad, d.IdPais AS Pais, p.NumLineas, "
                   "p.UnidadesTotales, p.ImporteTotal, p.FechaPedido, p.FechaInicioFabricacion, p.FechaListoEnvio, "
                   "p.FechaCaducidad, p.FechaLimiteEntrega, p.HorasDisponiblesReparto, p.Estado "
                   "FROM Pedidos p JOIN Clientes c ON c.IdCliente = p.IdCliente "
                   "JOIN Destinos d ON d.IdDestino = p.IdDestino ORDER BY p.FechaLimiteEntrega, p.IdPedido")
    st.dataframe(ped, use_container_width=True, hide_index=True)

# --- Parámetros --------------------------------------------------------------
with tab_par:
    a, b = st.columns(2)
    a.subheader("Coste por km de cada camión")
    a.dataframe(consulta("SELECT TipoVehiculo, CapacidadUnidades, PrecioNetoLitro, CosteCombustibleKm, CostePeajeKm, "
                         "CosteMantenimientoKm, CosteFijoKm, CosteConductorKm, CosteTotalKm, KgCO2Km "
                         "FROM vw_CosteKmTipoVehiculo"), use_container_width=True, hide_index=True)
    b.subheader("Parámetros del sistema")
    b.dataframe(consulta("SELECT Clave, Valor, Unidad, Descripcion FROM ParametrosSistema ORDER BY Clave"),
                use_container_width=True, hide_index=True)
    st.subheader("Precios de combustible")
    st.dataframe(consulta("SELECT pc.IdPais, tc.Nombre AS Combustible, pc.FechaDesde, pc.PrecioLitro, pc.Fuente "
                          "FROM PreciosCombustible pc JOIN TiposCombustible tc ON tc.IdCombustible = pc.IdCombustible "
                          "ORDER BY pc.IdPais, tc.Nombre"), use_container_width=True, hide_index=True)
    st.caption("Los valores económicos son referencias orientativas; se cambian en la base de datos.")
