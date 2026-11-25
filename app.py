"""Interfaz del prototipo: planificador de rutas de IA DELIVERY SL.

Ejecutar con:  .venv/Scripts/streamlit run app.py

Páginas (menú lateral):
    Simulación en tiempo real  Elige una planificación y una ruta y reprodúcela: el camión se mueve
                               por el mapa con su conductor, carga, velocidad, pausas y descansos.
    Planificar                 Calcula una planificación nueva (OR-Tools, Clarke-Wright o envío directo).
    Comparativa                Compara las planificaciones guardadas.
    Pedidos                    Pedidos con sus fechas de fabricación y caducidad.
    Flota y conductores        Camiones y conductores, y su trabajo en una planificación.
    Parámetros                 Costes, normativa y precios que usa el optimizador.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from optimizador.datos import cargar_escenario, conectar, listar_escenarios, listar_tipos_vehiculo
from optimizador.persistencia import guardar_solucion
from optimizador.planificador import planificar
from optimizador.simulacion import cargar_rutas, carga_de_pedidos, datos_animacion, viaje_de_ruta

st.set_page_config(page_title="IA DELIVERY · Planificador de rutas", page_icon="🚚", layout="wide")

PLANTILLA = Path(__file__).parent / "interfaz" / "simulacion.html"
ALGORITMOS = {"OR-Tools": "ortools", "Clarke-Wright": "clarke-wright", "Envío directo (un camión por pedido)": "directo"}
PAGINAS = ["🚚 Simulación en tiempo real", "🧭 Planificar", "📊 Comparativa", "📦 Pedidos",
           "👥 Flota y conductores", "⚙️ Parámetros"]

st.markdown("""
<style>
  .block-container { padding-top: 1.6rem; }
  [data-testid="stMetric"] { background: rgba(127,127,127,.06); border: 1px solid rgba(127,127,127,.18);
                             border-radius: 12px; padding: 10px 14px; }
  [data-testid="stMetricLabel"] { font-size: .85rem; }
  .cabecera { display:flex; align-items:center; gap:14px; margin-bottom:.4rem; }
  .cabecera .logo { font-size:2.1rem; }
  .cabecera h1 { margin:0; font-size:1.7rem; }
  .cabecera p { margin:0; opacity:.7; }
  .chip { display:inline-block; padding:2px 10px; border-radius:999px; background:rgba(225,29,72,.12);
          color:#e11d48; font-weight:600; font-size:.8rem; margin-right:6px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
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


def miles(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


@st.cache_data(show_spinner=False)
def rutas_de_planificacion(id_plan: int):
    """Escenario, matriz de km y rutas de una planificación (en caché por IdPlanificacion)."""
    conn = conectar()
    try:
        return cargar_rutas(conn, id_plan)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def carga(ids: tuple[int, ...]) -> dict:
    conn = conectar()
    try:
        return carga_de_pedidos(conn, list(ids))
    finally:
        conn.close()


def resumen_planes() -> pd.DataFrame:
    return consulta("SELECT IdPlanificacion AS Plan, Algoritmo, TipoVehiculo AS Camion, NumCamiones, NumRutas AS Viajes, "
                    "ROUND(KmTotales) AS Km, CosteTotal, ROUND(KgCO2 / 1000, 1) AS CO2_t, OcupacionMediaPct, "
                    "PedidosPlanificados, PedidosFueraDePlazo, TiempoCalculoSeg, FechaEjecucion "
                    "FROM vw_ResumenPlanificacion ORDER BY IdPlanificacion DESC")


def etiqueta_plan(fila) -> str:
    return (f"Plan {fila['Plan']} · {fila['Algoritmo']} · {fila['Camion'].replace('frigorífico bitemperatura ', '')}"
            f" · {fila['NumCamiones']} camiones")


def ir_a_simulacion(id_plan: int) -> None:
    st.session_state["plan"] = id_plan
    st.session_state["pagina"] = PAGINAS[0]


# ---------------------------------------------------------------------------
# Cabecera y menú
# ---------------------------------------------------------------------------
try:
    _conn = conectar()
    with _conn.cursor() as _cur:
        ESCENARIOS = listar_escenarios(_cur)
        TIPOS = listar_tipos_vehiculo(_cur)
    _conn.close()
except Exception as e:  # noqa: BLE001 - se muestra cualquier fallo de conexión al usuario
    st.error(f"No se puede conectar con la base de datos BDIADelivery: {e}")
    st.info("Arranca MySQL en XAMPP o configura BDIA_HOST, BDIA_USER y BDIA_PASSWORD.")
    st.stop()

with st.sidebar:
    st.markdown("### 🚚 IA DELIVERY SL")
    st.caption("Reparto de perecederos desde Mataró")
    pagina = st.radio("Menú", PAGINAS, key="pagina", label_visibility="collapsed")
    st.divider()
    st.caption("Proyecto 1 · Máster FP IA y Big Data (Stucom)")

st.markdown(f"""<div class="cabecera"><div class="logo">🚚</div><div>
<h1>{pagina.split(' ', 1)[1]}</h1><p>Plataforma de distribución de mercancías perecederas · España, Portugal y Andorra</p>
</div></div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Simulación en tiempo real
# ---------------------------------------------------------------------------
def pagina_simulacion() -> None:
    planes = resumen_planes()
    if planes.empty:
        st.info("Todavía no hay planificaciones. Calcula una en la página Planificar.")
        return
    ids = planes["Plan"].tolist()
    defecto = ids.index(st.session_state["plan"]) if st.session_state.get("plan") in ids else 0
    id_plan = st.selectbox("Planificación", ids, index=defecto,
                           format_func=lambda i: etiqueta_plan(planes[planes["Plan"] == i].iloc[0]))
    st.session_state["plan"] = id_plan

    with st.spinner("Cargando rutas…"):
        esc, km, rutas = rutas_de_planificacion(int(id_plan))

    tabla = pd.DataFrame([{
        "Camión": r["NumCamion"], "Viaje": r["NumViaje"], "Matrícula": r["Matricula"] or "—",
        "Conductor": r["Conductor"] or "Sin asignar",
        "Ruta": " → ".join(["Mataró"] + [p["Ciudad"] for p in r["Paradas"]] + ["Mataró"]),
        "Paradas": len(r["Paradas"]), "Unidades": r["UnidadesCargadas"], "Km": round(float(r["KmTotales"])),
        "Salida": r["FechaSalida"], "Regreso": r["FechaRegreso"],
    } for r in rutas])

    st.markdown("**Elige una ruta** (haz clic en una fila) para verla en el mapa:")
    sel = st.dataframe(tabla, hide_index=True, use_container_width=True, height=230,
                       on_select="rerun", selection_mode="single-row", key=f"rutas_{id_plan}")
    fila = sel.selection.rows[0] if sel.selection.rows else 0
    ruta = rutas[fila]

    viaje = viaje_de_ruta(esc, km, ruta)
    carga_pedidos = carga(tuple(p.pedido.id for p in viaje.paradas))
    datos = datos_animacion(esc, viaje, ruta, carga_pedidos)
    html = PLANTILLA.read_text(encoding="utf-8").replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False))
    components.html(html, height=640, scrolling=False)

    pausas = sum(1 for e in viaje.eventos if e["tipo"] == "pausa")
    descansos = sum(1 for e in viaje.eventos if e["tipo"] == "descanso")
    st.markdown(f"<span class='chip'>👤 {ruta['Conductor'] or 'Conductor sin asignar'}</span>"
                f"<span class='chip'>🚛 {ruta['Matricula'] or '—'} · {esc.tipo.nombre}</span>"
                f"<span class='chip'>🕒 {viaje.salida:%d/%m %H:%M} → {viaje.regreso:%d/%m %H:%M}</span>",
                unsafe_allow_html=True)
    k = st.columns(5)
    k[0].metric("Paradas", len(viaje.paradas))
    k[1].metric("Horas al volante", f"{viaje.horas_conduccion:.1f} h")
    k[2].metric("Pausas · descansos", f"{pausas} · {descansos}")
    k[3].metric("Coste del viaje", euros(viaje.coste_total))
    k[4].metric("CO2", f"{viaje.kg_co2:,.0f} kg".replace(",", "."))

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("##### 📦 Qué transporta")
        filas = [{"Pedido": p.pedido.id, "Destino": ruta["Paradas"][i]["Ciudad"], "Familia": c["categoria"],
                  "Temperatura": c["regimen"], "Unidades": c["unidades"], "Líneas": c["lineas"]}
                 for i, p in enumerate(viaje.paradas) for c in carga_pedidos.get(p.pedido.id, [])]
        st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True, height=280)
    with c2:
        st.markdown("##### 🗓️ Itinerario")
        st.dataframe(pd.DataFrame([{
            "#": n, "Destino": ruta["Paradas"][n - 1]["Ciudad"], "Llegada": p.llegada.strftime("%d/%m %H:%M"),
            "Límite": p.pedido.limite.strftime("%d/%m %H:%M"),
            "Margen (h)": round((p.pedido.limite - p.llegada).total_seconds() / 3600),
        } for n, p in enumerate(viaje.paradas, start=1)]), hide_index=True, use_container_width=True, height=280)


# ---------------------------------------------------------------------------
# Planificar
# ---------------------------------------------------------------------------
def pagina_planificar() -> None:
    c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
    esc_sel = c1.selectbox("Escenario", ESCENARIOS, format_func=lambda e: f"{e['Nombre']} ({e['Pedidos']} pedidos)")
    tipo_sel = c2.selectbox("Camión (flota homogénea)", TIPOS,
                            format_func=lambda t: f"{t['TipoVehiculo']} · {miles(t['CapacidadUnidades'])} uds")
    alg_nombre = c3.selectbox("Algoritmo", list(ALGORITMOS))
    segundos = c4.number_input("Segundos", 5, 300, 30, help="Tiempo máximo de búsqueda de OR-Tools")
    guardar = st.checkbox("Guardar la planificación (necesario para verla en la simulación)", value=True)

    if st.button("🧭 Calcular rutas", type="primary"):
        with st.spinner("Calculando rutas, flota mínima y conductores…"):
            conn = conectar()
            try:
                esc = cargar_escenario(conn, esc_sel["IdEscenario"], tipo_sel["IdTipoVehiculo"])
                sol = planificar(esc, ALGORITMOS[alg_nombre], segundos=int(segundos))
                id_plan = guardar_solucion(conn, esc, sol) if guardar else None
            finally:
                conn.close()
        st.session_state["ultima"] = (esc, sol, id_plan)

    if "ultima" not in st.session_state:
        st.info("Elige los parámetros y pulsa **Calcular rutas**.")
        return
    esc, sol, id_plan = st.session_state["ultima"]
    ahorro = sol.coste_externalizado - sol.coste_total
    k = st.columns(3) + st.columns(3)
    k[0].metric("Camiones necesarios", sol.num_camiones)
    k[1].metric("Viajes", len(sol.viajes))
    k[2].metric("Km totales", miles(sol.km_total))
    k[3].metric("Coste flota propia", euros(sol.coste_total))
    k[4].metric("Frente a externalizar", euros(ahorro), delta="ahorro" if ahorro > 0 else "sobrecoste",
                delta_color="normal" if ahorro > 0 else "inverse")
    k[5].metric("CO2", f"{sol.kg_co2 / 1000:.1f} t")
    st.caption(f"{sol.algoritmo} · {esc.tipo.nombre} · {sol.pedidos_fuera_plazo} pedidos fuera de plazo · "
               f"calculado en {sol.tiempo_calculo_s:.1f} s")
    if id_plan:
        st.button(f"🚚 Ver la planificación {id_plan} en la simulación", on_click=ir_a_simulacion, args=(id_plan,))
    st.dataframe(pd.DataFrame([{
        "Camión": c, "Viaje": nv, "Pedidos": ", ".join(map(str, v.ids_pedidos)), "Unidades": v.unidades,
        "Ocupación %": round(100 * v.unidades / esc.tipo.capacidad, 1), "Salida": v.salida, "Regreso": v.regreso,
        "Km": round(v.km_total), "Coste €": round(v.coste_total, 2), "Holgura h": round(v.holgura_h, 1),
    } for c, indices in enumerate(sol.camiones, start=1) for nv, v in
        ((nv, sol.viajes[i]) for nv, i in enumerate(indices, start=1))]), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Comparativa
# ---------------------------------------------------------------------------
def pagina_comparativa() -> None:
    res = resumen_planes()
    if res.empty:
        st.info("Todavía no hay planificaciones guardadas.")
        return
    res["CosteTotal"] = res["CosteTotal"].astype(float)
    mejor = res.loc[res["CosteTotal"].idxmin()]
    k = st.columns(4)
    k[0].metric("Planificaciones", len(res))
    k[1].metric("Mejor coste", euros(mejor["CosteTotal"]), help=etiqueta_plan(mejor))
    k[2].metric("Menos camiones", int(res["NumCamiones"].min()))
    k[3].metric("Pedidos fuera de plazo", int(res["PedidosFueraDePlazo"].max()))
    res["Etiqueta"] = res["Plan"].astype(str) + " · " + res["Algoritmo"] + " · " + \
        res["Camion"].str.extract(r"(\d+ t)")[0].fillna("")
    g = st.columns(3)
    g[0].bar_chart(res.set_index("Etiqueta")["CosteTotal"], y_label="Coste (€)", color="#e11d48")
    g[1].bar_chart(res.set_index("Etiqueta")["NumCamiones"], y_label="Camiones", color="#2563eb")
    g[2].bar_chart(res.set_index("Etiqueta")["CO2_t"].astype(float), y_label="CO2 (t)", color="#16a34a")
    st.dataframe(res.drop(columns="Etiqueta"), use_container_width=True, hide_index=True)
    plan = st.selectbox("Abrir en la simulación", res["Plan"].tolist(),
                        format_func=lambda i: etiqueta_plan(res[res["Plan"] == i].iloc[0]))
    st.button("🚚 Ver en la simulación", on_click=ir_a_simulacion, args=(int(plan),))


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------
def pagina_pedidos() -> None:
    ped = consulta("SELECT p.IdPedido, p.IdEscenario, c.Nombre AS Cliente, d.Ciudad, d.IdPais AS Pais, p.NumLineas, "
                   "p.UnidadesTotales, p.ImporteTotal, p.FechaPedido, p.FechaInicioFabricacion, p.FechaListoEnvio, "
                   "p.FechaCaducidad, p.FechaLimiteEntrega, p.HorasDisponiblesReparto, p.Estado "
                   "FROM Pedidos p JOIN Clientes c ON c.IdCliente = p.IdCliente "
                   "JOIN Destinos d ON d.IdDestino = p.IdDestino ORDER BY p.FechaLimiteEntrega, p.IdPedido")
    paises = st.multiselect("País", sorted(ped["Pais"].unique()), default=sorted(ped["Pais"].unique()))
    ped = ped[ped["Pais"].isin(paises)]
    k = st.columns(4)
    k[0].metric("Pedidos", len(ped))
    k[1].metric("Unidades", miles(ped["UnidadesTotales"].sum()))
    k[2].metric("Importe", euros(float(ped["ImporteTotal"].sum())))
    k[3].metric("Horas de reparto (mín.)", int(ped["HorasDisponiblesReparto"].min()) if len(ped) else 0)
    st.dataframe(ped, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Flota y conductores
# ---------------------------------------------------------------------------
def pagina_flota() -> None:
    planes = resumen_planes()
    id_plan = st.selectbox("Trabajo en la planificación", planes["Plan"].tolist() if not planes.empty else [None],
                           format_func=lambda i: etiqueta_plan(planes[planes["Plan"] == i].iloc[0]) if i else "—")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🚛 Camiones")
        st.dataframe(consulta(
            "SELECT v.Matricula, t.Nombre AS Tipo, v.KmActuales, v.Estado, COUNT(r.IdRuta) AS Viajes, "
            "ROUND(COALESCE(SUM(r.KmTotales), 0)) AS KmPlan "
            "FROM Vehiculos v JOIN TiposVehiculo t ON t.IdTipoVehiculo = v.IdTipoVehiculo "
            "LEFT JOIN Rutas r ON r.IdVehiculo = v.IdVehiculo AND r.IdPlanificacion = %s "
            "GROUP BY v.IdVehiculo, v.Matricula, t.Nombre, v.KmActuales, v.Estado ORDER BY Viajes DESC, v.IdVehiculo",
            (id_plan,)), use_container_width=True, hide_index=True, height=420)
    with c2:
        st.markdown("##### 👥 Conductores")
        st.dataframe(consulta(
            "SELECT c.Nombre, c.CosteHoraEmpresa AS EurHora, COUNT(r.IdRuta) AS Viajes, "
            "ROUND(COALESCE(SUM(r.HorasConduccion), 0), 1) AS HorasVolante, ROUND(COALESCE(SUM(r.KmTotales), 0)) AS Km "
            "FROM Conductores c LEFT JOIN Rutas r ON r.IdConductor = c.IdConductor AND r.IdPlanificacion = %s "
            "GROUP BY c.IdConductor, c.Nombre, c.CosteHoraEmpresa ORDER BY Viajes DESC, c.Nombre",
            (id_plan,)), use_container_width=True, hide_index=True, height=420)
    st.caption("Nombres, DNI y matrículas ficticios (database/05_flota_conductores.sql).")


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
def pagina_parametros() -> None:
    a, b = st.columns(2)
    a.markdown("##### Coste por km de cada camión")
    a.dataframe(consulta("SELECT TipoVehiculo, CapacidadUnidades, PrecioNetoLitro, CosteCombustibleKm, CostePeajeKm, "
                         "CosteMantenimientoKm, CosteFijoKm, CosteConductorKm, CosteTotalKm, KgCO2Km "
                         "FROM vw_CosteKmTipoVehiculo"), use_container_width=True, hide_index=True)
    b.markdown("##### Parámetros del sistema")
    b.dataframe(consulta("SELECT Clave, Valor, Unidad, Descripcion FROM ParametrosSistema ORDER BY Clave"),
                use_container_width=True, hide_index=True)
    st.markdown("##### Precios de combustible")
    st.dataframe(consulta("SELECT pc.IdPais, tc.Nombre AS Combustible, pc.FechaDesde, pc.PrecioLitro, pc.Fuente "
                          "FROM PreciosCombustible pc JOIN TiposCombustible tc ON tc.IdCombustible = pc.IdCombustible "
                          "ORDER BY pc.IdPais, tc.Nombre"), use_container_width=True, hide_index=True)
    st.caption("Los valores económicos son referencias orientativas; se cambian en la base de datos.")


{
    PAGINAS[0]: pagina_simulacion, PAGINAS[1]: pagina_planificar, PAGINAS[2]: pagina_comparativa,
    PAGINAS[3]: pagina_pedidos, PAGINAS[4]: pagina_flota, PAGINAS[5]: pagina_parametros,
}[pagina]()
