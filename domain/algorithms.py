# domain\algorithms.py
from typing import List, Tuple, Optional
import pandas as pd
import networkx as nx

from infrastructure.geo_utils import distancia_km


def asignacion_greedy(
    pacientes_df: pd.DataFrame, hospitales_df: pd.DataFrame, lista_pacientes: List[str]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Heurística greedy:
      - Ordena pacientes por gravedad (Crítico -> Moderado -> Leve).
      - Para cada paciente busca el hospital más cercano con capacidad.
      - Si paciente crítico, prioriza camas UCI cuando existan.
    Retorna (asign_df, hospitales_estado_df).
    """
    hosp = hospitales_df.copy().reset_index(drop=True)

    # Asegurar tipos
    hosp["Capacidad_Camas"] = hosp["Capacidad_Camas"].astype(int)
    if "Camas_UCI" not in hosp.columns:
        hosp["Camas_UCI"] = 0
    else:
        hosp["Camas_UCI"] = hosp["Camas_UCI"].astype(int)

    gravedad_order = {"crítico": 0, "critico": 0, "crit": 0, "moderado": 1, "leve": 2}
    pacientes_sel = pacientes_df[pacientes_df["ID_Paciente"].isin(lista_pacientes)].copy()
    pacientes_sel["g_order"] = pacientes_sel["Gravedad"].map(lambda x: gravedad_order.get(str(x).strip().lower(), 2))
    pacientes_sel = pacientes_sel.sort_values("g_order")

    resultados = []
    for _, p in pacientes_sel.iterrows():
        lat_p, lon_p = float(p["Latitud"]), float(p["Longitud"])
        hosp["dist_km"] = hosp.apply(
            lambda r: distancia_km(lat_p, lon_p, float(r["Latitud"]), float(r["Longitud"])),
            axis=1,
        )
        hosp_sorted = hosp.sort_values("dist_km").reset_index(drop=True)

        asignado = False
        gravedad = str(p["Gravedad"]).strip().lower()
        # Si crítico, priorizar UCI
        if gravedad.startswith("c"):
            uci_candidatos = hosp_sorted[hosp_sorted["Camas_UCI"] > 0]
            for _, h in uci_candidatos.iterrows():
                if h["Capacidad_Camas"] > 0:
                    resultados.append((p["ID_Paciente"], h["ID_Hospital"], float(h["dist_km"])))
                    hosp.loc[hosp["ID_Hospital"] == h["ID_Hospital"], "Capacidad_Camas"] -= 1
                    hosp.loc[hosp["ID_Hospital"] == h["ID_Hospital"], "Camas_UCI"] -= 1
                    asignado = True
                    break
        # Si no asignado aún, asignar al hospital más cercano con cama
        if not asignado:
            for _, h in hosp_sorted.iterrows():
                if h["Capacidad_Camas"] > 0:
                    resultados.append((p["ID_Paciente"], h["ID_Hospital"], float(h["dist_km"])))
                    hosp.loc[hosp["ID_Hospital"] == h["ID_Hospital"], "Capacidad_Camas"] -= 1
                    asignado = True
                    break
        if not asignado:
            resultados.append((p["ID_Paciente"], None, None))

    asign_df = pd.DataFrame(resultados, columns=["ID_Paciente", "ID_Hospital", "dist_km"])
    return asign_df, hosp


def construir_grafo_flow(pacientes_df: pd.DataFrame, hospitales_df: pd.DataFrame) -> nx.DiGraph:
    """
    Construye grafo dirigido para network_simplex (min-cost flow).
    Nodos: S, pacientes, hospitales, T.
    Aristas:
      - S->paciente (cap=1, weight=0)
      - paciente->hospital (cap=1, weight = cost)
      - hospital->T (cap = Capacidad_Camas, weight=0)
    """
    G = nx.DiGraph()
    S = "S"
    T = "T"
    G.add_node(S)
    G.add_node(T)

    gravedad_factor = {"Crítico": 1.0, "Critico": 1.0, "Crit": 1.0, "Moderado": 1.2, "Leve": 1.5}

    # S -> pacientes
    for _, p in pacientes_df.iterrows():
        pid = p["ID_Paciente"]
        G.add_node(pid)
        G.add_edge(S, pid, capacity=1, weight=0)

    # hospitales -> T
    for _, h in hospitales_df.iterrows():
        hid = h["ID_Hospital"]
        cap = int(h["Capacidad_Camas"])
        G.add_node(hid)
        if cap > 0:
            G.add_edge(hid, T, capacity=cap, weight=0)
        else:
            # Si cap == 0, agregar arista con capacity 0 (no influye)
            G.add_edge(hid, T, capacity=0, weight=0)

    # paciente -> hospital
    for _, p in pacientes_df.iterrows():
        lat_p, lon_p = float(p["Latitud"]), float(p["Longitud"])
        gf = float(gravedad_factor.get(str(p["Gravedad"]).strip(), 1.2))
        pid = p["ID_Paciente"]
        for _, h in hospitales_df.iterrows():
            lat_h, lon_h = float(h["Latitud"]), float(h["Longitud"])
            dist = distancia_km(lat_p, lon_p, lat_h, lon_h)
            # transformar a entero para evitar problemas con floats en weights
            cost = int(max(1, round(dist * 100 * gf)))
            G.add_edge(pid, h["ID_Hospital"], capacity=1, weight=cost)

    return G


def asignacion_min_cost_flow(pacientes_df: pd.DataFrame, hospitales_df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Ejecuta network_simplex y devuelve DataFrame de asignaciones:
    columnas: ID_Paciente, ID_Hospital, dist_km
    En caso de error devuelve (empty_df, error_str).
    """
    try:
        G = construir_grafo_flow(pacientes_df, hospitales_df)
        flow_cost, flow_dict = nx.network_simplex(G)
        asignaciones = []
        for pid in pacientes_df["ID_Paciente"]:
            assigned_hospital = None
            for hid, flow in flow_dict.get(pid, {}).items():
                if flow and flow > 0:
                    assigned_hospital = hid
                    break
            if assigned_hospital and assigned_hospital != "T":
                p_row = pacientes_df[pacientes_df["ID_Paciente"] == pid].iloc[0]
                h_row = hospitales_df[hospitales_df["ID_Hospital"] == assigned_hospital].iloc[0]
                d = distancia_km(float(p_row["Latitud"]), float(p_row["Longitud"]), float(h_row["Latitud"]), float(h_row["Longitud"]))
                asignaciones.append((pid, assigned_hospital, d))
            else:
                asignaciones.append((pid, None, None))
        return pd.DataFrame(asignaciones, columns=["ID_Paciente", "ID_Hospital", "dist_km"]), None
    except Exception as e:
        return pd.DataFrame([], columns=["ID_Paciente", "ID_Hospital", "dist_km"]), str(e)


def hospital_tiene_especialidad(hospital_row: pd.Series, especialidad_requerida: str) -> bool:
    """
    Verifica si un hospital tiene la especialidad requerida.
    
    Args:
        hospital_row: Fila del DataFrame de hospitales
        especialidad_requerida: Especialidad a buscar (ej: "Cardiología")
        
    Returns:
        True si el hospital tiene la especialidad
    """
    if "Especialidades" not in hospital_row or pd.isna(hospital_row["Especialidades"]):
        return False
    
    especialidades = str(hospital_row["Especialidades"]).lower()
    return especialidad_requerida.lower() in especialidades


def filtrar_hospitales_por_especialidad(
    hospitales_df: pd.DataFrame, 
    especialidad: str,
    requiere_camas: bool = True
) -> pd.DataFrame:
    """
    Filtra hospitales que tienen una especialidad específica.
    
    Args:
        hospitales_df: DataFrame de hospitales
        especialidad: Especialidad requerida
        requiere_camas: Si True, solo retorna hospitales con camas disponibles
        
    Returns:
        DataFrame filtrado
    """
    if especialidad == "" or especialidad.lower() == "ninguna":
        return hospitales_df.copy()
    
    filtrados = hospitales_df[
        hospitales_df.apply(lambda row: hospital_tiene_especialidad(row, especialidad), axis=1)
    ].copy()
    
    if requiere_camas:
        filtrados = filtrados[filtrados["Capacidad_Camas"] > 0]
    
    return filtrados


def encontrar_hospitales_disponibles_con_especialidad(
    hospitales_df: pd.DataFrame,
    departamento: str,
    especialidad: str
) -> pd.DataFrame:
    """
    Encuentra hospitales disponibles con especialidad en un departamento.
    
    Args:
        hospitales_df: DataFrame de hospitales
        departamento: Departamento a filtrar
        especialidad: Especialidad requerida
        
    Returns:
        DataFrame de hospitales que cumplen criterios
    """
    # Filtrar por departamento
    if "Departamento" in hospitales_df.columns:
        hosp_dept = hospitales_df[hospitales_df["Departamento"] == departamento].copy()
    else:
        hosp_dept = hospitales_df.copy()
    
    # Filtrar por especialidad y disponibilidad
    return filtrar_hospitales_por_especialidad(hosp_dept, especialidad, requiere_camas=True)