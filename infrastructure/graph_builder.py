import pandas as pd
import networkx as nx
from typing import Dict, List, Optional, Set, Tuple
from infrastructure.geo_utils import distancia_km


class GraphBuilder:
    """Construye grafos de hospitales por departamento."""

    def __init__(self, hospitales_df: pd.DataFrame):
        self.hospitales_df = hospitales_df
        self.grafos_departamentos: Dict[str, nx.Graph] = {}
        self._build_all_graphs()

    def _build_all_graphs(self):
        """Pre-construye grafos para todos los departamentos disponibles."""
        if "Departamento" not in self.hospitales_df.columns:
            # Fallback: usar todos los hospitales en un solo grafo
            self.grafos_departamentos["TODOS"] = self._build_graph_for_hospitals(
                self.hospitales_df
            )
            return

        departamentos = self.hospitales_df["Departamento"].unique()
        for dep in departamentos:
            hosp_dep = self.hospitales_df[
                self.hospitales_df["Departamento"] == dep
            ].copy()
            if len(hosp_dep) > 0:
                self.grafos_departamentos[dep] = self._build_graph_for_hospitals(
                    hosp_dep
                )

    def _build_graph_for_hospitals(self, hospitales: pd.DataFrame) -> nx.Graph:
        """
        Construye grafo no dirigido conectando todos los hospitales entre sí.
        Peso de arista = distancia euclidiana (Haversine) en km.
        """
        G = nx.Graph()

        # Agregar nodos
        for _, h in hospitales.iterrows():
            G.add_node(
                h["ID_Hospital"],
                latitud=float(h["Latitud"]),
                longitud=float(h["Longitud"]),
                nombre=h.get("Nombre", ""),
                camas=int(h.get("Capacidad_Camas", 0)),
                camas_uci=int(h.get("Camas_UCI", 0)),
                especialidades=h.get("Especialidades", ""),
                departamento=h.get("Departamento", ""),
            )

        # Agregar aristas (conectar todos con todos)
        nodos = list(G.nodes())
        for i, nodo1 in enumerate(nodos):
            for nodo2 in nodos[i + 1 :]:
                data1 = G.nodes[nodo1]
                data2 = G.nodes[nodo2]
                dist = distancia_km(
                    data1["latitud"],
                    data1["longitud"],
                    data2["latitud"],
                    data2["longitud"],
                )
                G.add_edge(nodo1, nodo2, weight=dist)

        return G

    def get_graph(self, departamento: str) -> Optional[nx.Graph]:
        """Obtiene el grafo de un departamento específico."""
        return self.grafos_departamentos.get(departamento)

    def get_all_departments(self) -> List[str]:
        """Retorna lista de departamentos disponibles."""
        return list(self.grafos_departamentos.keys())

    def find_nearest_hospital_with_specialty(
        self,
        departamento: str,
        especialidad: str,
        paciente_lat: float,
        paciente_lon: float,
        requiere_disponibilidad: bool = True,
    ) -> Optional[str]:
        """
        Encuentra el hospital más cercano en el departamento con la especialidad requerida.
        
        Args:
            departamento: Departamento a buscar
            especialidad: Especialidad requerida
            paciente_lat: Latitud del paciente
            paciente_lon: Longitud del paciente
            requiere_disponibilidad: Si True, solo considera hospitales con camas > 0
        
        Returns:
            ID_Hospital o None si no hay disponible
        """
        grafo = self.get_graph(departamento)
        if not grafo:
            return None

        candidatos = []
        for nodo in grafo.nodes():
            data = grafo.nodes[nodo]
            especialidades = str(data.get("especialidades", "")).lower()
            
            # Verificar especialidad
            if especialidad.lower() not in especialidades:
                continue
            
            # Verificar disponibilidad si se requiere
            if requiere_disponibilidad and data.get("camas", 0) <= 0:
                continue
            
            # Calcular distancia
            dist = distancia_km(
                paciente_lat,
                paciente_lon,
                data["latitud"],
                data["longitud"],
            )
            candidatos.append((nodo, dist))

        if candidatos:
            candidatos.sort(key=lambda x: x[1])
            return candidatos[0][0]
        return None

    def get_border_hospitals(self, departamento: str, top_k: int = 3) -> List[str]:
        """
        Identifica hospitales 'frontera' del departamento.
        Heurística: los más cercanos al centroide de OTROS departamentos.
        
        Para simplificar, retornamos los top_k hospitales con más conexiones.
        En implementación real, calcularías cercanía geográfica a fronteras.
        """
        grafo = self.get_graph(departamento)
        if not grafo:
            return []

        # Simplificación: nodos con mayor grado (más conexiones)
        degrees = dict(grafo.degree())
        sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
        return [node for node, _ in sorted_nodes[:top_k]]

    def merge_graphs(self, dep1: str, dep2: str) -> nx.Graph:
        """
        Une dos grafos de departamentos.
        Conecta los hospitales frontera más cercanos entre ambos.
        """
        g1 = self.get_graph(dep1)
        g2 = self.get_graph(dep2)

        if not g1 or not g2:
            return g1 or g2 or nx.Graph()

        # Crear grafo unido
        G_merged = nx.compose(g1, g2)

        # Conectar hospitales frontera más cercanos
        border1 = self.get_border_hospitals(dep1, top_k=2)
        border2 = self.get_border_hospitals(dep2, top_k=2)

        for h1 in border1:
            for h2 in border2:
                data1 = G_merged.nodes[h1]
                data2 = G_merged.nodes[h2]
                dist = distancia_km(
                    data1["latitud"],
                    data1["longitud"],
                    data2["latitud"],
                    data2["longitud"],
                )
                G_merged.add_edge(h1, h2, weight=dist, is_border_connection=True)

        return G_merged

    def find_nearest_department_with_specialty(
        self,
        current_dept: str,
        especialidad: str,
        paciente_lat: float,
        paciente_lon: float,
    ) -> Optional[str]:
        """
        Encuentra el departamento vecino más cercano que tenga la especialidad.
        
        Returns:
            Nombre del departamento o None
        """
        departamentos = [d for d in self.get_all_departments() if d != current_dept]

        candidatos = []
        for dep in departamentos:
            # NUEVO: Buscar hospital SIN requerir disponibilidad primero
            hospital = self.find_nearest_hospital_with_specialty(
                dep, especialidad, paciente_lat, paciente_lon,
                requiere_disponibilidad=False  # No filtrar por camas aquí
            )
            if hospital:
                grafo = self.get_graph(dep)
                data = grafo.nodes[hospital]
                dist = distancia_km(
                    paciente_lat,
                    paciente_lon,
                    data["latitud"],
                    data["longitud"],
                )
                # Guardar departamento, hospital y distancia
                candidatos.append((dep, hospital, dist, data.get("camas", 0)))

        if candidatos:
            # Priorizar departamentos con camas disponibles, luego por distancia
            candidatos.sort(key=lambda x: (x[3] <= 0, x[2]))  # (sin_camas, distancia)
            return candidatos[0][0]  # Retornar solo el departamento
        return None

    def find_nearest_hospital_in_department(
        self,
        departamento: str,
        especialidad: str,
        paciente_lat: float,
        paciente_lon: float,
    ) -> Optional[Tuple[str, float, int]]:
        """
        Encuentra el hospital más cercano con especialidad en un departamento.
        Retorna el hospital aunque no tenga camas disponibles.
        
        Returns:
            Tupla (hospital_id, distancia_km, camas_disponibles) o None
        """
        grafo = self.get_graph(departamento)
        if not grafo:
            return None

        candidatos = []
        for nodo in grafo.nodes():
            data = grafo.nodes[nodo]
            especialidades = str(data.get("especialidades", "")).lower()
            
            if especialidad.lower() in especialidades:
                dist = distancia_km(
                    paciente_lat,
                    paciente_lon,
                    data["latitud"],
                    data["longitud"],
                )
                camas = data.get("camas", 0)
                candidatos.append((nodo, dist, camas))

        if candidatos:
            # Ordenar: primero por tener camas, luego por distancia
            candidatos.sort(key=lambda x: (x[2] <= 0, x[1]))
            return candidatos[0]
        return None