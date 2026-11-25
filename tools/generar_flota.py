"""Genera database/05_flota_conductores.sql: camiones y conductores FICTICIOS.

Uso: python tools/generar_flota.py database/05_flota_conductores.sql

Los nombres se combinan al azar a partir de listas de nombres y apellidos
frecuentes, y los DNI y matrículas son inventados: no corresponden a personas
ni vehículos reales. La generación es reproducible (semilla fija).
"""

import random
import sys

NOMBRES = ["Antonio", "Manuel", "José", "Francisco", "David", "Juan", "Javier", "Daniel", "Carlos", "Jesús",
           "Alejandro", "Miguel", "Rafael", "Pablo", "Sergio", "Fernando", "Jorge", "Alberto", "Luis", "Álvaro",
           "María", "Carmen", "Ana", "Laura", "Marta", "Elena", "Lucía", "Cristina", "Paula", "Sara",
           "Rui", "João", "Pedro", "Tiago", "Inês", "Joana", "Jordi", "Montse", "Núria", "Xavier"]
APELLIDOS = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez",
             "Martín", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso",
             "Gutiérrez", "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Serrano", "Blanco",
             "Molina", "Morales", "Ortega", "Delgado", "Castro", "Ortiz", "Rubio", "Marín", "Sanz", "Iglesias",
             "Silva", "Pereira", "Costa", "Puig", "Ferrer", "Vidal", "Soler"]
LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"
CONSONANTES = "BCDFGHJKLMNPRSTVWXYZ"
FLOTA = {1: 40, 2: 20, 3: 10}      # IdTipoVehiculo -> número de camiones
NUM_CONDUCTORES = 60


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main(salida: str) -> None:
    rnd = random.Random(2026)
    usados: set[str] = set()
    conductores = []
    while len(conductores) < NUM_CONDUCTORES:
        nombre = f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
        if nombre in usados:
            continue
        usados.add(nombre)
        numero = 90_000_000 + len(conductores) + 1          # rango ficticio
        dni = f"{numero}{LETRAS_DNI[numero % 23]}"
        coste = rnd.choice([21.0, 22.0, 22.5, 23.0, 24.0])
        conductores.append((nombre, dni, coste))

    vehiculos = []
    n = 0
    for tipo, cuantos in FLOTA.items():
        for _ in range(cuantos):
            n += 1
            letras = "".join(rnd.choice(CONSONANTES) for _ in range(3))
            vehiculos.append((f"{n:04d} {letras}", tipo, rnd.randint(5_000, 180_000)))

    lineas = [
        "-- =====================================================================",
        "-- BDIADelivery - CAMIONES Y CONDUCTORES (DATOS FICTICIOS)",
        "-- Generado con tools/generar_flota.py. Ejecutar después de 01 a 04.",
        "-- Nombres, DNI y matrículas inventados: no corresponden a personas ni",
        "-- vehículos reales.",
        "-- =====================================================================",
        "",
        "USE `BDIADelivery`;",
        "SET NAMES utf8mb4;",
        "",
        "INSERT INTO `Vehiculos` (`Matricula`, `IdTipoVehiculo`, `IdAlmacen`, `FechaAlta`, `KmActuales`) VALUES",
        ",\n".join(f"({q(m)}, {t}, 1, '2026-01-15', {km})" for m, t, km in vehiculos) + ";",
        "",
        "INSERT INTO `Conductores` (`Nombre`, `DNI`, `IdAlmacen`, `CosteHoraEmpresa`, `FechaAlta`) VALUES",
        ",\n".join(f"({q(nm)}, {q(d)}, 1, {c:.2f}, '2026-01-15')" for nm, d, c in conductores) + ";",
        "",
        "SELECT (SELECT COUNT(*) FROM `Vehiculos`) AS Vehiculos, (SELECT COUNT(*) FROM `Conductores`) AS Conductores;",
        "",
    ]
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas))


if __name__ == "__main__":
    main(sys.argv[1])
