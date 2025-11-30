# presentation/__init__.py
"""
Módulo de presentación - Interfaz de usuario con Streamlit
"""

from .ui_routes import show_routes_module
from .ui_graphs_optimized import show_graphs_module

__all__ = [
    'show_routes_module',
    'show_graphs_module',
]