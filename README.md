# GYF Care

Aplicación de demo para asignación inteligente de pacientes a hospitales usando teoría de grafos y algoritmos de optimización.

## Estructura del proyecto

- `application/assignment_service.py` — servicio de aplicación que orquesta algoritmos y actualiza estado.
- `domain/algorithms.py` — algoritmos: greedy y min-cost flow.
- `domain/entities.py` — dataclasses del dominio (opcional).
- `infrastructure/data_loader.py` — carga de CSV (cacheada).
- `infrastructure/geo_utils.py` — funciones de distancia / hospitales cercanos.
- `presentation/ui_map.py` — pestaña del mapa.
- `presentation/ui_graph.py` — pestaña del grafo.
- `presentation/ui_assignment.py` — pestaña de asignación (interactiva).
- `shared/config.py` — constantes de configuración.
- `data/` — tus CSV (`pacientes.csv`, `hospitales.csv`).

## Requisitos (ejemplo)

- streamlit
- pandas
- networkx
- haversine
- folium
- streamlit-folium
- matplotlib

## Instalar:

`pip install -r requirements.txt`

## Run:
`streamlit run streamlit_app.py`