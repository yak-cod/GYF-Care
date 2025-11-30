# application/route_service.py
import requests
import time
import json
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

    def _get_cache_path(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
    ) -> Path:
        """Genera el path del archivo de caché para una ruta."""
        cache_key = (
            f"{start_coords[0]:.6f}_{start_coords[1]:.6f}_"
            f"to_{end_coords[0]:.6f}_{end_coords[1]:.6f}"
        )
        return self.cache_dir / f"route_{cache_key}.json"

    def _load_from_cache(self, cache_path: Path) -> Optional[Dict]:
        """Carga ruta desde caché si existe."""
        if not ENABLE_ROUTE_CACHE or not cache_path.exists():
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_to_cache(self, cache_path: Path, data: Dict) -> None:
        """Guarda ruta en caché."""
        if not ENABLE_ROUTE_CACHE:
            return
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            # Si falla la caché, no rompemos el flujo principal
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

        Returns:
            Dict con:
                - geometry: Lista de coordenadas [[lon, lat], ...] (formato ORS)
                - distance: Distancia en kilómetros (float)
                - duration: Duración en minutos (float)
                - success: bool
                - error/details si falla
        """
        start_coords = (start_lat, start_lon)
        end_coords = (end_lat, end_lon)

        # 1) Verificar caché
        cache_path = self._get_cache_path(start_coords, end_coords)
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return cached_data

        # Formato ORS: coordinates = [[lon, lat], [lon, lat]]
        coordinates = [[start_lon, start_lat], [end_lon, end_lat]]

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        # radiuses: permite buscar una vía hasta 1000 m alrededor de cada punto
        body = {
            "coordinates": coordinates,
            "radiuses": [1000, 1000],
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

                    # Formato GeoJSON
                    if "features" in data and len(data["features"]) > 0:
                        feature = data["features"][0]
                        geometry = feature["geometry"]["coordinates"]
                        segments = feature["properties"].get("segments", [])
                        if not segments:
                            return {
                                "success": False,
                                "error": "No segments in GeoJSON response",
                                "details": data,
                            }
                        properties = segments[0]

                        result = {
                            "geometry": geometry,  # [[lon, lat], ...]
                            "distance": properties.get("distance", 0) / 1000.0,
                            "duration": properties.get("duration", 0) / 60.0,
                            "success": True,
                        }

                        self._save_to_cache(cache_path, result)
                        return result

                    # Formato JSON estándar (no GeoJSON)
                    elif "routes" in data and len(data["routes"]) > 0:
                        route = data["routes"][0]

                        geometry = None
                        # Si viene polilínea codificada
                        geometry_encoded = route.get("geometry", "")
                        if geometry_encoded and isinstance(geometry_encoded, str):
                            import polyline

                            decoded = polyline.decode(geometry_encoded)
                            # polyline → [(lat, lon), ...] → convertimos a [[lon, lat], ...]
                            geometry = [[lon, lat] for lat, lon in decoded]
                        else:
                            # Segments con geometry explícita
                            segments = route.get("segments") or []
                            if segments and "geometry" in segments[0]:
                                geometry = segments[0]["geometry"]

                        if not geometry:
                            return {
                                "success": False,
                                "error": "No geometry found in response",
                                "details": data,
                            }

                        summary = route.get("summary", {})
                        result = {
                            "geometry": geometry,
                            "distance": summary.get("distance", 0) / 1000.0,
                            "duration": summary.get("duration", 0) / 60.0,
                            "success": True,
                        }

                        self._save_to_cache(cache_path, result)
                        return result

                    else:
                        return {
                            "success": False,
                            "error": "No route found in response",
                            "details": data,
                        }

                # Rate limit
                elif response.status_code == 429:
                    if attempt < ORS_MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)  # backoff exponencial
                        continue
                    return {
                        "success": False,
                        "error": "Rate limit exceeded. Try again later.",
                        "details": response.text,
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
            origins: lista de (lat, lon)
            destinations: lista de (lat, lon)

        Returns:
            Lista de dicts de resultado, uno por cada par origen–destino.
        """
        results: List[Optional[Dict]] = []
        for origin, destination in zip(origins, destinations):
            route = self.get_route(
                start_lat=origin[0],
                start_lon=origin[1],
                end_lat=destination[0],
                end_lon=destination[1],
            )
            results.append(route)
            # pequeña pausa para no saturar la API
            time.sleep(0.1)
        return results
