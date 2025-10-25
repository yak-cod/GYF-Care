import requests
import time
import json
import os
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from shared.config import (
    ORS_API_KEY,
    ORS_DIRECTIONS_ENDPOINT,
    ORS_MAX_RETRIES,
    ORS_TIMEOUT,
    CACHE_DIR,
    ENABLE_ROUTE_CACHE,
)


class RouteService:
    """Servicio para obtener rutas reales usando OpenRouteService API."""

    def __init__(self):
        self.api_key = ORS_API_KEY
        self.endpoint = ORS_DIRECTIONS_ENDPOINT
        self.cache_dir = Path(CACHE_DIR)
        if ENABLE_ROUTE_CACHE:
            self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> Path:
        """Genera path del archivo de caché para una ruta."""
        cache_key = f"{start_coords[0]:.6f}_{start_coords[1]:.6f}_to_{end_coords[0]:.6f}_{end_coords[1]:.6f}"
        return self.cache_dir / f"route_{cache_key}.json"

    def _load_from_cache(self, cache_path: Path) -> Optional[Dict]:
        """Carga ruta desde caché si existe."""
        if not ENABLE_ROUTE_CACHE or not cache_path.exists():
            return None
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_to_cache(self, cache_path: Path, data: Dict):
        """Guarda ruta en caché."""
        if not ENABLE_ROUTE_CACHE:
            return
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> Optional[Dict]:
        """
        Obtiene ruta entre dos puntos usando ORS API.
        
        Args:
            start_lat: Latitud de inicio
            start_lon: Longitud de inicio
            end_lat: Latitud de destino
            end_lon: Longitud de destino
            
        Returns:
            Dict con:
                - geometry: Lista de coordenadas [[lon, lat], ...] para Folium
                - distance: Distancia en kilómetros
                - duration: Duración en minutos
                - success: bool
                - error: str (si hay error)
        """
        start_coords = (start_lat, start_lon)
        end_coords = (end_lat, end_lon)
        
        # Verificar caché
        cache_path = self._get_cache_path(start_coords, end_coords)
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return cached_data

        # Formato ORS: coordinates son [lon, lat] (no lat, lon)
        coordinates = [[start_lon, start_lat], [end_lon, end_lat]]
        
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        
        body = {
            "coordinates": coordinates,
        }

        for attempt in range(ORS_MAX_RETRIES):
            try:
                response = requests.post(
                    self.endpoint,
                    json=body,
                    headers=headers,
                    timeout=ORS_TIMEOUT,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # ORS puede responder en dos formatos: GeoJSON o JSON estándar
                    # Intentar formato GeoJSON primero
                    if "features" in data and len(data["features"]) > 0:
                        feature = data["features"][0]
                        geometry = feature["geometry"]["coordinates"]
                        properties = feature["properties"]["segments"][0]
                        
                        result = {
                            "geometry": geometry,  # [[lon, lat], ...]
                            "distance": properties["distance"] / 1000,  # convertir m a km
                            "duration": properties["duration"] / 60,  # convertir s a min
                            "success": True,
                        }
                        
                        # Guardar en caché
                        self._save_to_cache(cache_path, result)
                        return result
                    
                    # Intentar formato JSON estándar
                    elif "routes" in data and len(data["routes"]) > 0:
                        route = data["routes"][0]
                        
                        # Decodificar geometría encoded polyline
                        import polyline
                        geometry_encoded = route.get("geometry", "")
                        
                        # Si la geometría está encoded, decodificarla
                        if geometry_encoded and isinstance(geometry_encoded, str):
                            # polyline devuelve [(lat, lon), ...], necesitamos [[lon, lat], ...]
                            decoded = polyline.decode(geometry_encoded)
                            geometry = [[lon, lat] for lat, lon in decoded]
                        else:
                            # Si no está encoded, puede estar en route['segments'][0]['geometry']
                            geometry = None
                            if "segments" in route and len(route["segments"]) > 0:
                                segment = route["segments"][0]
                                if "geometry" in segment:
                                    geometry = segment["geometry"]
                        
                        if not geometry:
                            return {
                                "success": False,
                                "error": "No geometry found in response",
                                "details": f"Response: {data}",
                            }
                        
                        summary = route.get("summary", {})
                        
                        result = {
                            "geometry": geometry,
                            "distance": summary.get("distance", 0) / 1000,  # m a km
                            "duration": summary.get("duration", 0) / 60,  # s a min
                            "success": True,
                        }
                        
                        # Guardar en caché
                        self._save_to_cache(cache_path, result)
                        return result
                    
                    else:
                        return {
                            "success": False,
                            "error": "No route found in response",
                            "details": f"Response: {data}",
                        }
                
                elif response.status_code == 429:  # Rate limit
                    if attempt < ORS_MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)  # exponential backoff
                        continue
                    return {
                        "success": False,
                        "error": "Rate limit exceeded. Try again later.",
                    }
                
                else:
                    error_detail = response.text if response.text else f"Status {response.status_code}"
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_detail,
                    }
                    
            except requests.Timeout:
                if attempt < ORS_MAX_RETRIES - 1:
                    continue
                return {
                    "success": False,
                    "error": "Request timeout",
                }
            except Exception as e:
                if attempt < ORS_MAX_RETRIES - 1:
                    continue
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}",
                }
        
        return {
            "success": False,
            "error": "Max retries exceeded",
        }

    def get_multiple_routes(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
    ) -> List[Optional[Dict]]:
        """
        Obtiene múltiples rutas. Útil para calcular varias rutas a la vez.
        
        Args:
            origins: Lista de (lat, lon) de origen
            destinations: Lista de (lat, lon) de destino
            
        Returns:
            Lista de resultados (uno por cada par origin-destination)
        """
        results = []
        for origin, destination in zip(origins, destinations):
            route = self.get_route(origin[0], origin[1], destination[0], destination[1])
            results.append(route)
            # Pequeña pausa para no saturar la API
            time.sleep(0.1)
        return results