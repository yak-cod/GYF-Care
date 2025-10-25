# infrastructure\ufds_service.py
from typing import Dict, Optional, Set


class UnionFind:
    """
    Estructura de datos Union-Find (Disjoint Set Union) para manejar
    la unión de grafos de departamentos.
    """

    def __init__(self, elements: list):
        """
        Inicializa UFDS con elementos dados.
        
        Args:
            elements: Lista de identificadores (ej: nombres de departamentos)
        """
        self.parent: Dict = {elem: elem for elem in elements}
        self.rank: Dict[str, int] = {elem: 0 for elem in elements}
        self.size: Dict[str, int] = {elem: 1 for elem in elements}

    def find(self, x: str) -> str:
        """
        Encuentra el representante (raíz) del conjunto que contiene x.
        Usa path compression para optimización.
        """
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, x: str, y: str) -> bool:
        """
        Une los conjuntos que contienen x e y.
        Usa union by rank para mantener árbol balanceado.
        
        Returns:
            True si se realizó la unión, False si ya estaban en el mismo conjunto
        """
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return False  # Ya están en el mismo conjunto

        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
            self.size[root_y] += self.size[root_x]
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
            self.size[root_x] += self.size[root_y]
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
            self.size[root_x] += self.size[root_y]

        return True

    def connected(self, x: str, y: str) -> bool:
        """Verifica si x e y están en el mismo conjunto."""
        return self.find(x) == self.find(y)

    def get_component_size(self, x: str) -> int:
        """Retorna el tamaño del componente que contiene x."""
        root = self.find(x)
        return self.size[root]

    def get_all_components(self) -> Dict[str, Set[str]]:
        """
        Retorna todos los componentes conectados.
        
        Returns:
            Dict {root: {elementos del componente}}
        """
        components: Dict[str, Set[str]] = {}
        for elem in self.parent.keys():
            root = self.find(elem)
            if root not in components:
                components[root] = set()
            components[root].add(elem)
        return components


class DepartmentUnionService:
    """
    Servicio para manejar la unión de departamentos cuando un paciente
    necesita especialización no disponible en su departamento.
    """

    def __init__(self, departamentos: list):
        self.ufds = UnionFind(departamentos)
        self.merged_departments: Set[tuple] = set()  # Pares de departamentos unidos

    def merge_departments(self, dept1: str, dept2: str) -> bool:
        """
        Une dos departamentos en el UFDS.
        
        Returns:
            True si se realizó la unión, False si ya estaban unidos
        """
        if self.ufds.union(dept1, dept2):
            # Guardar el par ordenado
            pair = tuple(sorted([dept1, dept2]))
            self.merged_departments.add(pair)
            return True
        return False

    def are_connected(self, dept1: str, dept2: str) -> bool:
        """Verifica si dos departamentos están conectados."""
        return self.ufds.connected(dept1, dept2)

    def get_merged_pairs(self) -> list:
        """Retorna lista de pares de departamentos que han sido unidos."""
        return list(self.merged_departments)

    def get_connected_departments(self, dept: str) -> Set[str]:
        """
        Retorna todos los departamentos conectados al departamento dado.
        """
        components = self.ufds.get_all_components()
        root = self.ufds.find(dept)
        return components.get(root, {dept})

    def reset(self, departamentos: list):
        """Reinicia el UFDS con nuevos departamentos."""
        self.ufds = UnionFind(departamentos)
        self.merged_departments.clear()