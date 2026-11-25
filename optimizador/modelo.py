"""Clases de datos del optimizador.

Son estructuras simples (dataclasses) sin lógica de base de datos, para que el
algoritmo se pueda probar con datos sintéticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Pedido:
    """Pedido a entregar en un destino.

    listo:   momento en que el pedido está fabricado y el almacén abre (puede cargarse).
    limite:  momento máximo de entrega (caducidad menos el margen de seguridad).
    """

    id: int
    id_destino: int
    lat: float
    lon: float
    unidades: int
    listo: datetime
    limite: datetime
    caducidad: datetime
    descarga_h: float = 0.5
    pais: str = "ES"


@dataclass(frozen=True)
class TipoVehiculo:
    """Tipo de camión de la flota (homogénea) y sus costes por km."""

    id: int
    nombre: str
    capacidad: int
    velocidad_kmh: float
    litros_km: float
    kg_co2_km: float
    coste_combustible_km: float
    coste_peaje_km: float
    coste_mantenimiento_km: float
    coste_fijo_km: float
    precio_adquisicion: float = 0.0

    @property
    def coste_km_sin_conductor(self) -> float:
        """Coste variable y fijo imputado por km, sin contar al conductor."""
        return self.coste_combustible_km + self.coste_peaje_km + self.coste_mantenimiento_km + self.coste_fijo_km


@dataclass(frozen=True)
class Parametros:
    """Parámetros de negocio y de normativa (tabla ParametrosSistema)."""

    factor_carretera: float = 1.25
    coste_conductor_h: float = 22.0
    dieta_dia: float = 55.0
    pernocta: float = 45.0
    conduccion_max_diaria_h: float = 9.0
    conduccion_continua_max_h: float = 4.5
    pausa_h: float = 0.75
    descanso_diario_h: float = 11.0
    carga_h: float = 1.0


@dataclass(frozen=True)
class Almacen:
    id: int
    nombre: str
    lat: float
    lon: float


@dataclass(frozen=True)
class TarifaExterna:
    """Tarifa del operador logístico externo: fijo + km de ida + unidades."""

    fijo_envio: float
    coste_km: float
    coste_unidad: float


@dataclass
class Escenario:
    """Todo lo necesario para planificar: pedidos, almacén, camión y parámetros."""

    id: int
    almacen: Almacen
    pedidos: list[Pedido]
    tipo: TipoVehiculo
    params: Parametros = field(default_factory=Parametros)
    tarifa: TarifaExterna | None = None


@dataclass
class Parada:
    pedido: Pedido
    km_desde_anterior: float
    llegada: datetime
    salida: datetime


@dataclass
class Viaje:
    """Un viaje de un camión: sale de Mataró, entrega sus pedidos y vuelve."""

    paradas: list[Parada]
    salida: datetime
    regreso: datetime
    km_total: float
    horas_conduccion: float
    horas_trabajo: float
    pernoctas: int
    unidades: int
    litros: float
    kg_co2: float
    coste_combustible: float
    coste_peajes: float
    coste_mantenimiento: float
    coste_fijo: float
    coste_conductor: float
    coste_dietas: float
    factible: bool
    motivo: str = ""
    eventos: list[dict] = field(default_factory=list)   # línea de tiempo del conductor (ver tiempos.py)

    @property
    def coste_total(self) -> float:
        return (self.coste_combustible + self.coste_peajes + self.coste_mantenimiento
                + self.coste_fijo + self.coste_conductor + self.coste_dietas)

    @property
    def ids_pedidos(self) -> list[int]:
        return [p.pedido.id for p in self.paradas]

    @property
    def holgura_h(self) -> float:
        """Horas que se puede retrasar la salida sin que ninguna entrega pase su límite."""
        return min((p.pedido.limite - p.llegada).total_seconds() / 3600 for p in self.paradas)


@dataclass
class Solucion:
    """Resultado de una planificación."""

    algoritmo: str
    viajes: list[Viaje]
    camiones: list[list[int]]          # índices de self.viajes asignados a cada camión, en orden
    tiempo_calculo_s: float
    parametros_algoritmo: dict = field(default_factory=dict)
    coste_externalizado: float = 0.0   # mismo reparto con el operador externo

    @property
    def num_camiones(self) -> int:
        return len(self.camiones)

    @property
    def km_total(self) -> float:
        return sum(v.km_total for v in self.viajes)

    @property
    def coste_total(self) -> float:
        return sum(v.coste_total for v in self.viajes)

    @property
    def kg_co2(self) -> float:
        return sum(v.kg_co2 for v in self.viajes)

    @property
    def pedidos_fuera_plazo(self) -> int:
        return sum(1 for v in self.viajes for p in v.paradas if p.llegada > p.pedido.limite)
