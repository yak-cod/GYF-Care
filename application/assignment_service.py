from typing import Tuple, Optional
import pandas as pd

from domain.algorithms import asignacion_greedy, asignacion_min_cost_flow
from infrastructure.geo_utils import distancia_km


def run_greedy(pacientes_df: pd.DataFrame, hosp_state_df: pd.DataFrame, pacientes_list) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ejecuta la heurística greedy y retorna (asign_df, hosp_state_nuevo).
    Nota: asignacion_greedy ya devuelve hosp actualizado.
    """
    asign_df, hosp_nuevo = asignacion_greedy(pacientes_df, hosp_state_df, pacientes_list)
    return asign_df, hosp_nuevo


def run_min_cost_flow(pacientes_df: pd.DataFrame, hosp_state_df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str], pd.DataFrame]:
    """
    Ejecuta min-cost flow, y aplica la actualización de camas al estado de hospitales.
    Retorna (asign_df, error_message_or_None, hosp_state_nuevo)
    """
    asign_df, error = asignacion_min_cost_flow(pacientes_df, hosp_state_df)
    if error:
        return asign_df, error, hosp_state_df.copy()

    # aplicar decrementos a hosp_state_df según asignaciones
    hosp_nuevo = hosp_state_df.copy().reset_index(drop=True)
    # contar asignaciones por hospital
    asign_count = asign_df[asign_df["ID_Hospital"].notnull()].groupby("ID_Hospital").size().to_dict()

    for hid, cnt in asign_count.items():
        mask = hosp_nuevo["ID_Hospital"] == hid
        if mask.any():
            hosp_nuevo.loc[mask, "Capacidad_Camas"] = hosp_nuevo.loc[mask, "Capacidad_Camas"].astype(int) - cnt
            # no sabemos si asignación usó UCI; para simplificar no restamos UCI aquí
            # si quieres restar UCI cuando paciente crítico, necesitaríamos pacientes_df para saberlo
            # (podemos mejorar esto en el futuro)
            hosp_nuevo.loc[mask, "Capacidad_Camas"] = hosp_nuevo.loc[mask, "Capacidad_Camas"].clip(lower=0)

    return asign_df, None, hosp_nuevo
