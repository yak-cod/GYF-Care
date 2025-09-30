from dataclasses import dataclass
from typing import Optional


@dataclass
class Patient:
    id: str
    gravedad: str
    distrito: Optional[str]
    latitud: float
    longitud: float


@dataclass
class Hospital:
    id: str
    nombre: str
    capacidad_camas: int
    camas_uci: int
    distrito: Optional[str]
    latitud: float
    longitud: float
