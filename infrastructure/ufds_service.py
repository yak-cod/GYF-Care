# infrastructure/ufds_service.py
"""
Union-Find Disjoint Set (UFDS) optimizado con:
- Union by Rank: Mantiene árboles balanceados
- Path Compression: Optimiza búsquedas
- Log de operaciones para visualización educativa

Similar a la implementación de VisuAlgo.
"""

from typing import Dict, Optional, Set, List, Tuple


class UnionFind:
    """
    Estructura de datos Union-Find (Disjoint Set Union) optimizada.
    
    Implementa:
    1. Union by Rank: Une conjuntos manteniendo árbol balanceado
    2. Path Compression: Comprime caminos en Find para O(α(n))
    
    Complejidad amortizada: O(α(n)) ≈ O(1) para ambas operaciones
    donde α es la inversa de Ackermann (crece extremadamente lento).
    """

    def __init__(self, elements: list):
        """
        Inicializa UFDS con elementos independientes.
        
        Args:
            elements: Lista de identificadores (ej: departamentos)
        """
        # parent[x] = padre de x (si x es raíz, parent[x] = x mismo)
        self.parent: Dict[str, str] = {elem: elem for elem in elements}
        
        # rank[x] = altura aproximada del árbol con raíz x
        # Usado para union by rank
        self.rank: Dict[str, int] = {elem: 0 for elem in elements}
        
        # size[x] = número de elementos en el conjunto de x
        # Solo es preciso cuando x es una raíz
        self.size: Dict[str, int] = {elem: 1 for elem in elements}

    def find(self, x: str) -> str:
        """
        Encuentra el representante (raíz) del conjunto que contiene x.
        
        Implementa PATH COMPRESSION:
        - Al buscar la raíz, hace que todos los nodos en el camino
          apunten directamente a ella
        - Esto optimiza futuras búsquedas
        
        Ejemplo:
            Antes:  4 -> 3 -> 2 -> 1 (raíz)
            Después: 4 -> 1, 3 -> 1, 2 -> 1
        
        Complejidad: O(α(n)) amortizado
        
        Args:
            x: Elemento a buscar
            
        Returns:
            Raíz del conjunto que contiene x
        """
        if x not in self.parent:
            # Elemento no existe, retornarlo como raíz de sí mismo
            self.parent[x] = x
            self.rank[x] = 0
            self.size[x] = 1
            return x
        
        # Si x es su propio padre, es la raíz
        if self.parent[x] == x:
            return x
        
        # Path compression: hacer que x apunte directamente a la raíz
        # Recursivamente encuentra la raíz y actualiza parent[x]
        self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> bool:
        """
        Une los conjuntos que contienen x e y.
        
        Implementa UNION BY RANK:
        - Une el árbol con menor rank al de mayor rank
        - Si tienen igual rank, uno se convierte en raíz y su rank aumenta
        - Esto mantiene los árboles balanceados
        
        Ejemplo (union by rank):
            rank[A] = 2, rank[B] = 1
            → B se une a A (A tiene mayor rank)
            → rank[A] sigue siendo 2
            
            rank[A] = 1, rank[B] = 1
            → B se une a A
            → rank[A] = 2 (aumenta porque eran iguales)
        
        Complejidad: O(α(n)) amortizado
        
        Args:
            x: Elemento del primer conjunto
            y: Elemento del segundo conjunto
            
        Returns:
            True si se realizó la unión
            False si ya estaban en el mismo conjunto
        """
        # Encontrar raíces de ambos elementos
        root_x = self.find(x)
        root_y = self.find(y)

        # Si ya están en el mismo conjunto, no hacer nada
        if root_x == root_y:
            return False

        # UNION BY RANK:
        # Unir el árbol con menor rank al de mayor rank
        
        if self.rank[root_x] < self.rank[root_y]:
            # root_y tiene mayor rank → root_y será la nueva raíz
            self.parent[root_x] = root_y
            self.size[root_y] += self.size[root_x]
            
        elif self.rank[root_x] > self.rank[root_y]:
            # root_x tiene mayor rank → root_x será la nueva raíz
            self.parent[root_y] = root_x
            self.size[root_x] += self.size[root_y]
            
        else:
            # Ranks iguales → elegir root_y como raíz
            # y aumentar su rank en 1
            self.parent[root_x] = root_y
            self.rank[root_y] += 1
            self.size[root_y] += self.size[root_x]

        return True

    def connected(self, x: str, y: str) -> bool:
        """
        Verifica si x e y están en el mismo conjunto.
        
        Args:
            x: Primer elemento
            y: Segundo elemento
            
        Returns:
            True si están en el mismo conjunto
        """
        return self.find(x) == self.find(y)

    def get_component_size(self, x: str) -> int:
        """
        Retorna el tamaño del componente que contiene x.
        
        Args:
            x: Elemento del conjunto
            
        Returns:
            Número de elementos en el conjunto
        """
        root = self.find(x)
        return self.size[root]

    def get_all_components(self) -> Dict[str, Set[str]]:
        """
        Retorna todos los componentes conectados.
        
        Returns:
            Dict {raíz: {elementos del componente}}
        """
        components: Dict[str, Set[str]] = {}
        for elem in self.parent.keys():
            root = self.find(elem)
            if root not in components:
                components[root] = set()
            components[root].add(elem)
        return components

    def get_parent_structure(self) -> Dict[str, str]:
        """
        Retorna la estructura de padres para visualización del árbol.
        
        Returns:
            Dict {elemento: padre}
        """
        structure = {}
        for elem in self.parent.keys():
            structure[elem] = self.parent[elem]
        return structure


class DepartmentUnionService:
    """
    Servicio para manejar la unión de departamentos mediante UFDS.
    
    """

    def __init__(self, departamentos: list):
        """
        Inicializa el servicio con lista de departamentos.
        
        Args:
            departamentos: Lista de nombres de departamentos
        """
        self.ufds = UnionFind(departamentos)
        self.merged_history: List[Tuple[str, str]] = []  # Pares unidos
        self.operation_log: List[Dict] = []  # Log detallado

    def merge_departments(self, dept1: str, dept2: str) -> bool:
        """
        Une dos departamentos usando Union-Find.
        
        Registra la operación completa para visualización:
        - Estado antes de la unión
        - Operación realizada
        - Estado después de la unión
        
        Args:
            dept1: Primer departamento
            dept2: Segundo departamento
            
        Returns:
            True si se realizó la unión
            False si ya estaban unidos
        """
        # Estado antes de la unión
        root1_before = self.ufds.find(dept1)
        root2_before = self.ufds.find(dept2)
        rank1_before = self.ufds.rank[root1_before]
        rank2_before = self.ufds.rank[root2_before]
        size1_before = self.ufds.size[root1_before]
        size2_before = self.ufds.size[root2_before]
        
        # Verificar si ya están unidos
        if root1_before == root2_before:
            self.operation_log.append({
                'operation': 'union_skip',
                'dept1': dept1,
                'dept2': dept2,
                'root': root1_before,
                'reason': 'already_connected',
                'message': f"  Union({dept1}, {dept2}): Ya están en el mismo conjunto (raíz: {root1_before})"
            })
            return False
        
        # Realizar la unión
        union_success = self.ufds.union(dept1, dept2)
        
        if union_success:
            # Estado después de la unión
            root_after = self.ufds.find(dept1)
            rank_after = self.ufds.rank[root_after]
            size_after = self.ufds.size[root_after]
            
            # Determinar qué raíz quedó
            if root_after == root1_before:
                operation_type = f"Union by Rank: {root2_before} → {root1_before}"
            else:
                operation_type = f"Union by Rank: {root1_before} → {root2_before}"
            
            # Registrar la unión exitosa
            self.merged_history.append((dept1, dept2))
            
            self.operation_log.append({
                'operation': 'union_success',
                'dept1': dept1,
                'dept2': dept2,
                'root1_before': root1_before,
                'root2_before': root2_before,
                'rank1_before': rank1_before,
                'rank2_before': rank2_before,
                'size1_before': size1_before,
                'size2_before': size2_before,
                'root_after': root_after,
                'rank_after': rank_after,
                'size_after': size_after,
                'operation_type': operation_type,
                'message': f"  Union({dept1}, {dept2}): {operation_type} | Tamaño: {size_after} | Rank: {rank_after}"
            })
            
            return True
        
        return False

    def are_connected(self, dept1: str, dept2: str) -> bool:
        """
        Verifica si dos departamentos están en el mismo conjunto.
        
        Args:
            dept1: Primer departamento
            dept2: Segundo departamento
            
        Returns:
            True si están conectados
        """
        return self.ufds.connected(dept1, dept2)

    def get_merged_pairs(self) -> List[Tuple[str, str]]:
        """
        Retorna lista de pares de departamentos unidos.
        
        Returns:
            Lista de tuplas (dept1, dept2)
        """
        return self.merged_history

    def get_connected_departments(self, dept: str) -> Set[str]:
        """
        Retorna todos los departamentos conectados a uno dado.
        
        Args:
            dept: Departamento de consulta
            
        Returns:
            Set de departamentos en el mismo componente
        """
        components = self.ufds.get_all_components()
        root = self.ufds.find(dept)
        return components.get(root, {dept})

    def get_operation_log(self) -> List[Dict]:
        """
        Retorna el log completo de operaciones.
        
        Returns:
            Lista de diccionarios con detalles de cada operación
        """
        return self.operation_log

    def get_tree_structure(self) -> Dict[str, str]:
        """
        Retorna la estructura del árbol UFDS.
        
        Returns:
            Dict {departamento: padre}
        """
        return self.ufds.get_parent_structure()

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas del UFDS.
        
        Returns:
            Dict con información estadística
        """
        components = self.ufds.get_all_components()
        
        return {
            'total_elements': len(self.ufds.parent),
            'num_components': len(components),
            'largest_component': max((len(comp) for comp in components.values()), default=0),
            'total_unions': len(self.merged_history),
            'components': {
                root: {
                    'members': list(members),
                    'size': len(members),
                    'rank': self.ufds.rank[root]
                }
                for root, members in components.items()
            }
        }

    def reset(self, departamentos: list):
        """
        Reinicia el UFDS con nuevos departamentos.
        
        Args:
            departamentos: Lista de departamentos
        """
        self.ufds = UnionFind(departamentos)
        self.merged_history.clear()
        self.operation_log.clear()

    def print_statistics(self):
        """
        Imprime estadísticas del UFDS en consola.
        Útil para debugging.
        """
        stats = self.get_statistics()
        print("=" * 50)
        print("ESTADÍSTICAS UFDS")
        print("=" * 50)
        print(f"Total elementos: {stats['total_elements']}")
        print(f"Número de componentes: {stats['num_components']}")
        print(f"Componente más grande: {stats['largest_component']}")
        print(f"Total de uniones: {stats['total_unions']}")
        print("\nComponentes:")
        for root, info in stats['components'].items():
            print(f"  Raíz: {root}")
            print(f"    Miembros: {', '.join(info['members'])}")
            print(f"    Tamaño: {info['size']}")
            print(f"    Rank: {info['rank']}")
        print("=" * 50)