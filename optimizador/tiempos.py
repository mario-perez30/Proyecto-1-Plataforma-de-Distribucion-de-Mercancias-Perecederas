"""Reloj del conductor según el Reglamento (CE) 561/2006 (simplificado).

Reglas aplicadas:
    * Tras 4,5 h de conducción continua, pausa de 45 min.
    * Máximo 9 h de conducción al día; después, descanso diario de 11 h.

Simplificaciones: no se modelan las ampliaciones a 10 h, los descansos
reducidos ni el límite semanal; las descargas no cuentan como pausa.

El reloj registra cada evento (conducción, pausa, descanso, carga, descarga)
con su hora de inicio y fin y la posición en el tramo, para poder reproducir
el viaje en la simulación en tiempo real.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .modelo import Parametros

_EPS = 1e-9


class RelojConductor:
    """Lleva la hora actual y las horas conducidas de un conductor durante un viaje."""

    def __init__(self, inicio: datetime, params: Parametros):
        self.t = inicio
        self.p = params
        self.conduccion_dia = 0.0       # horas conducidas desde el último descanso diario
        self.conduccion_continua = 0.0  # horas conducidas desde la última pausa
        self.horas_conduccion = 0.0
        self.horas_pausa = 0.0
        self.horas_otras = 0.0          # carga y descargas
        self.descansos_diarios = 0
        self.tramo = 0                  # tramo del viaje que se está recorriendo (0 = Mataró -> 1ª parada)
        self.eventos: list[dict] = []

    def _evento(self, tipo: str, inicio: datetime, fin: datetime, f0: float, f1: float) -> None:
        self.eventos.append({"tipo": tipo, "inicio": inicio, "fin": fin, "tramo": self.tramo, "f0": f0, "f1": f1})

    def conducir(self, horas: float) -> None:
        """Avanza el reloj conduciendo `horas`, intercalando pausas y descansos.

        Las fracciones f0/f1 de los eventos indican qué parte del tramo actual
        se ha recorrido (0 = inicio del tramo, 1 = final).
        """
        restante = horas
        hecho = 0.0
        while restante > _EPS:
            frac = hecho / horas if horas else 1.0
            if self.conduccion_dia >= self.p.conduccion_max_diaria_h - _EPS:
                fin = self.t + timedelta(hours=self.p.descanso_diario_h)
                self._evento("descanso", self.t, fin, frac, frac)
                self.t = fin
                self.conduccion_dia = 0.0
                self.conduccion_continua = 0.0
                self.descansos_diarios += 1
            if self.conduccion_continua >= self.p.conduccion_continua_max_h - _EPS:
                fin = self.t + timedelta(hours=self.p.pausa_h)
                self._evento("pausa", self.t, fin, frac, frac)
                self.t = fin
                self.horas_pausa += self.p.pausa_h
                self.conduccion_continua = 0.0
            tramo = min(restante,
                        self.p.conduccion_max_diaria_h - self.conduccion_dia,
                        self.p.conduccion_continua_max_h - self.conduccion_continua)
            fin = self.t + timedelta(hours=tramo)
            self._evento("conduccion", self.t, fin, hecho / horas, (hecho + tramo) / horas)
            self.t = fin
            self.conduccion_dia += tramo
            self.conduccion_continua += tramo
            self.horas_conduccion += tramo
            hecho += tramo
            restante -= tramo

    def trabajar(self, horas: float, tipo: str = "descarga") -> None:
        """Trabajo sin conducir (carga o descarga) en el punto actual."""
        fin = self.t + timedelta(hours=horas)
        self._evento(tipo, self.t, fin, 1.0 if tipo == "descarga" else 0.0, 1.0 if tipo == "descarga" else 0.0)
        self.t = fin
        self.horas_otras += horas

    @property
    def horas_trabajo(self) -> float:
        """Horas pagadas al conductor: conducción, pausas, carga y descargas."""
        return self.horas_conduccion + self.horas_pausa + self.horas_otras
