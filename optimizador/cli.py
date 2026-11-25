"""Línea de comandos del optimizador.

Ejemplos:
    python -m optimizador                                  # OR-Tools, escenario 1, camión 12 t
    python -m optimizador --algoritmo todos --tipo 2       # compara los tres algoritmos
    python -m optimizador --algoritmo clarke-wright --no-guardar
"""

from __future__ import annotations

import argparse

from .datos import cargar_escenario, conectar
from .persistencia import guardar_solucion
from .planificador import ALGORITMOS, planificar


def _euros(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m optimizador", description="Planifica las rutas de reparto.")
    ap.add_argument("--escenario", type=int, default=1, help="IdEscenario (por defecto 1)")
    ap.add_argument("--tipo", type=int, default=1, help="IdTipoVehiculo: 1 = 12 t, 2 = 18 t, 3 = 40 t")
    ap.add_argument("--algoritmo", choices=(*ALGORITMOS, "todos"), default="ortools")
    ap.add_argument("--segundos", type=int, default=30, help="Límite de tiempo de OR-Tools por oleada")
    ap.add_argument("--no-guardar", action="store_true", help="No guarda la planificación en la BD")
    args = ap.parse_args(argv)

    algoritmos = ALGORITMOS if args.algoritmo == "todos" else (args.algoritmo,)
    conn = conectar()
    try:
        esc = cargar_escenario(conn, args.escenario, args.tipo)
        print(f"Escenario {esc.id}: {len(esc.pedidos)} pedidos · camión: {esc.tipo.nombre}\n")
        cab = f"{'Algoritmo':<14}{'Camiones':>9}{'Viajes':>8}{'Km':>11}{'Coste':>13}{'Externo':>13}" \
              f"{'Ahorro':>12}{'CO2 (t)':>9}{'Fuera plazo':>12}{'Tiempo':>9}{'Plan':>6}"
        print(cab)
        print("-" * len(cab))
        for alg in algoritmos:
            sol = planificar(esc, alg, segundos=args.segundos)
            id_plan = "-" if args.no_guardar else guardar_solucion(conn, esc, sol)
            print(f"{alg:<14}{sol.num_camiones:>9}{len(sol.viajes):>8}{sol.km_total:>11,.0f}"
                  f"{_euros(sol.coste_total):>13}{_euros(sol.coste_externalizado):>13}"
                  f"{_euros(sol.coste_externalizado - sol.coste_total):>12}{sol.kg_co2 / 1000:>9.1f}"
                  f"{sol.pedidos_fuera_plazo:>12}{sol.tiempo_calculo_s:>8.1f}s{id_plan!s:>6}".replace(",", "."))
    finally:
        conn.close()
    return 0
