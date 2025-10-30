# application/assignment_service.py
from typing import Tuple, Optional, Dict, List
import pandas as pd
import networkx as nx

from domain.algorithms import (
    asignacion_greedy,
    asignacion_min_cost_flow,
    encontrar_hospitales_disponibles_con_especialidad,
)
from infrastructure.geo_utils import distancia_km
from infrastructure.graph_builder import GraphBuilder
from infrastructure.ufds_service import DepartmentUnionService
from infrastructure.route_service import RouteService


class AssignmentService:
    """Servicio de asignación con soporte para departamentos y especialidades."""

    def __init__(self, hospitales_df: pd.DataFrame):
        self.hospitales_df = hospitales_df
        self.graph_builder = GraphBuilder(hospitales_df)
        self.route_service = RouteService()
        self.ufds_service = None
        self._initialize_ufds()

    def _initialize_ufds(self):
        """Inicializa el servicio UFDS con todos los departamentos."""
        departamentos = self.graph_builder.get_all_departments()
        if departamentos:
            self.ufds_service = DepartmentUnionService(departamentos)

    def get_patient_department(self, paciente_row: pd.Series) -> str:
        """Extrae el departamento del paciente."""
        if "Departamento" in paciente_row:
            return str(paciente_row["Departamento"])
        # Fallback
        return "TODOS"

    def get_patient_specialty_required(self, paciente_row: pd.Series) -> Optional[str]:
        """
        Extrae la especialidad requerida del paciente basándose en su enfermedad.
        """
        if "Enfermedad" not in paciente_row:
            return None

        enfermedad = str(paciente_row["Enfermedad"]).lower()

        # Mapeo mejorado enfermedad
        mapeo_especialidades = {
            # Traumatología
            "tce": "Traumatología",
            "traumatismo": "Traumatología",
            "fractura": "Traumatología",
            "politraumatizado": "Traumatología",
            "trauma": "Traumatología",
            "quemaduras": "Traumatología",
            
            # Cardiología
            "cardio": "Cardiología",
            "corazón": "Cardiología",
            "infarto": "Cardiología",
            "insuficiencia cardíaca": "Cardiología",
            
            # Medicina Interna
            "neumonía": "Medicina Interna",
            "respiratorio": "Medicina Interna",
            "asma": "Medicina Interna",
            "diabetes": "Medicina Interna",
            "gastroenteritis": "Medicina Interna",
            "dengue": "Medicina Interna",
            "sepsis": "Medicina Interna",
            "intoxicación": "Medicina Interna",
            
            # Cirugía General
            "apendicitis": "Cirugía General",
            "colecistitis": "Cirugía General",
            "abdominal": "Cirugía General",
            
            # Nefrología
            "renal": "Nefrología",
            "riñón": "Nefrología",
            
            # Neurología
            "cerebro": "Neurología",
            "neurológico": "Neurología",
            "accidente cerebrovascular": "Neurología",
            "infarto cerebral": "Neurología",
            
            # Gineco-Obstetricia
            "parto": "Gineco-Obstetricia",
            "embarazo": "Gineco-Obstetricia",
            
            # Pediatría
            "pediatría": "Pediatría",
            "niño": "Pediatría",
        }

        for keyword, especialidad in mapeo_especialidades.items():
            if keyword in enfermedad:
                return especialidad

        return "Medicina Interna"  # Default

    def process_patient_assignment(
        self,
        paciente_row: pd.Series,
        hosp_state_df: pd.DataFrame,
    ) -> Dict:
        """
        Procesa la asignación de UN paciente considerando:
        1. Departamento del paciente
        2. Especialidad requerida
        3. Disponibilidad en su departamento
        4. UFDS para conectar con departamento vecino si es necesario
        
        Returns:
            Dict con información completa de la asignación
        """
        dept_paciente = self.get_patient_department(paciente_row)
        especialidad = self.get_patient_specialty_required(paciente_row)
        lat_p, lon_p = float(paciente_row["Latitud"]), float(paciente_row["Longitud"])

        resultado = {
            "hospital_asignado": None,
            "departamento_original": dept_paciente,
            "departamento_asignado": dept_paciente,
            "grafo_usado": None,
            "ufds_activado": False,
            "departamentos_unidos": [dept_paciente],
            "ruta": None,
            "mensaje": "",
            "distancia_km": None,
            "especialidad_buscada": especialidad,
        }

        # 1. Intentar encontrar hospital en el departamento del paciente
        hospitales_disponibles = encontrar_hospitales_disponibles_con_especialidad(
            hosp_state_df, dept_paciente, especialidad
        )

        # Si hay hospitales disponibles en el departamento
        if len(hospitales_disponibles) > 0:
            # Encontrar el más cercano
            hospitales_disponibles["dist_km"] = hospitales_disponibles.apply(
                lambda h: distancia_km(lat_p, lon_p, float(h["Latitud"]), float(h["Longitud"])),
                axis=1,
            )
            hospital_mas_cercano = hospitales_disponibles.sort_values("dist_km").iloc[0]

            resultado["hospital_asignado"] = hospital_mas_cercano["ID_Hospital"]
            resultado["grafo_usado"] = self.graph_builder.get_graph(dept_paciente)
            resultado["distancia_km"] = hospital_mas_cercano["dist_km"]
            resultado["mensaje"] = f"Hospital encontrado en {dept_paciente} con {especialidad}"

            # Obtener ruta real
            ruta = self.route_service.get_route(
                lat_p, lon_p,
                float(hospital_mas_cercano["Latitud"]),
                float(hospital_mas_cercano["Longitud"])
            )
            resultado["ruta"] = ruta

            return resultado

        # 2. No hay hospitales disponibles en el departamento → Activar UFDS
        print(f"No se encontró hospital con {especialidad} en {dept_paciente}. Activando UFDS...")
        
        if self.ufds_service and especialidad:
            dept_vecino = self.graph_builder.find_nearest_department_with_specialty(
                dept_paciente, especialidad, lat_p, lon_p
            )

            if dept_vecino:
                print(f"Departamento vecino encontrado: {dept_vecino}")
                
                # Unir departamentos con UFDS
                union_realizada = self.ufds_service.merge_departments(dept_paciente, dept_vecino)
                print(f"Unión UFDS: {union_realizada} ({dept_paciente} ↔ {dept_vecino})")

                # Crear grafo unido
                grafo_unido = self.graph_builder.merge_graphs(dept_paciente, dept_vecino)

                # Buscar hospitales disponibles en departamento vecino usando hosp_state_df
                hospitales_vecinos = encontrar_hospitales_disponibles_con_especialidad(
                    hosp_state_df, dept_vecino, especialidad
                )

                if len(hospitales_vecinos) > 0:
                    # Encontrar el más cercano
                    hospitales_vecinos["dist_km"] = hospitales_vecinos.apply(
                        lambda h: distancia_km(lat_p, lon_p, float(h["Latitud"]), float(h["Longitud"])),
                        axis=1,
                    )
                    hospital_mas_cercano = hospitales_vecinos.sort_values("dist_km").iloc[0]

                    resultado["hospital_asignado"] = hospital_mas_cercano["ID_Hospital"]
                    resultado["departamento_asignado"] = dept_vecino
                    resultado["grafo_usado"] = grafo_unido
                    resultado["ufds_activado"] = True
                    resultado["departamentos_unidos"] = [dept_paciente, dept_vecino]
                    resultado["distancia_km"] = hospital_mas_cercano["dist_km"]
                    resultado["mensaje"] = f"UFDS activado: {dept_paciente} ↔ {dept_vecino} | Hospital con {especialidad} encontrado"

                    # Obtener ruta real
                    ruta = self.route_service.get_route(
                        lat_p, lon_p,
                        float(hospital_mas_cercano["Latitud"]),
                        float(hospital_mas_cercano["Longitud"])
                    )
                    resultado["ruta"] = ruta

                    return resultado
                else:
                    print(f"No hay hospitales disponibles con {especialidad} en {dept_vecino}")
            else:
                print(f"No se encontró departamento vecino con {especialidad}")

        # 3. No se pudo asignar con UFDS - Buscar en CUALQUIER departamento
        print(f"Búsqueda ampliada: buscando {especialidad} en todos los departamentos...")
        
        todos_hospitales = hosp_state_df[hosp_state_df["Capacidad_Camas"] > 0].copy()
        
        # Filtrar por especialidad
        if especialidad:
            def tiene_especialidad(row):
                if pd.isna(row.get("Especialidades")):
                    return False
                return especialidad.lower() in str(row["Especialidades"]).lower()
            
            todos_hospitales = todos_hospitales[todos_hospitales.apply(tiene_especialidad, axis=1)]
        
        if len(todos_hospitales) > 0:
            # Calcular distancias
            todos_hospitales["dist_km"] = todos_hospitales.apply(
                lambda h: distancia_km(lat_p, lon_p, float(h["Latitud"]), float(h["Longitud"])),
                axis=1,
            )
            hospital_mas_cercano = todos_hospitales.sort_values("dist_km").iloc[0]
            dept_lejano = hospital_mas_cercano["Departamento"]
            
            # Unir con UFDS
            if self.ufds_service:
                self.ufds_service.merge_departments(dept_paciente, dept_lejano)
            
            resultado["hospital_asignado"] = hospital_mas_cercano["ID_Hospital"]
            resultado["departamento_asignado"] = dept_lejano
            resultado["grafo_usado"] = self.graph_builder.get_graph(dept_lejano)
            resultado["ufds_activado"] = True
            resultado["departamentos_unidos"] = [dept_paciente, dept_lejano]
            resultado["distancia_km"] = hospital_mas_cercano["dist_km"]
            resultado["mensaje"] = f"Búsqueda extendida: {dept_paciente} → {dept_lejano} ({hospital_mas_cercano['dist_km']:.1f} km)"
            
            # Obtener ruta
            ruta = self.route_service.get_route(
                lat_p, lon_p,
                float(hospital_mas_cercano["Latitud"]),
                float(hospital_mas_cercano["Longitud"])
            )
            resultado["ruta"] = ruta
            
            return resultado

        # 4. Realmente no hay nada disponible
        resultado["mensaje"] = f"No se encontró hospital disponible con {especialidad} en ningún departamento"
        return resultado


# Funciones legacy para compatibilidad con código existente
def run_greedy(
    pacientes_df: pd.DataFrame, hosp_state_df: pd.DataFrame, pacientes_list
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ejecuta la heurística greedy y retorna (asign_df, hosp_state_nuevo).
    """
    asign_df, hosp_nuevo = asignacion_greedy(pacientes_df, hosp_state_df, pacientes_list)
    return asign_df, hosp_nuevo


def run_min_cost_flow(
    pacientes_df: pd.DataFrame, hosp_state_df: pd.DataFrame
) -> Tuple[pd.DataFrame, Optional[str], pd.DataFrame]:
    """
    Ejecuta min-cost flow y aplica la actualización de camas.
    """
    asign_df, error = asignacion_min_cost_flow(pacientes_df, hosp_state_df)
    if error:
        return asign_df, error, hosp_state_df.copy()

    # aplicar decrementos a hosp_state_df según asignaciones
    hosp_nuevo = hosp_state_df.copy().reset_index(drop=True)
    asign_count = (
        asign_df[asign_df["ID_Hospital"].notnull()].groupby("ID_Hospital").size().to_dict()
    )

    for hid, cnt in asign_count.items():
        mask = hosp_nuevo["ID_Hospital"] == hid
        if mask.any():
            hosp_nuevo.loc[mask, "Capacidad_Camas"] = (
                hosp_nuevo.loc[mask, "Capacidad_Camas"].astype(int) - cnt
            )
            hosp_nuevo.loc[mask, "Capacidad_Camas"] = hosp_nuevo.loc[
                mask, "Capacidad_Camas"
            ].clip(lower=0)

    return asign_df, None, hosp_nuevo