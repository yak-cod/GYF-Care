# presentation/ui_backend_dashboard.py

import random

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from pyvis.network import Network

API_BASE = "http://localhost:5000/api"


# ================================
# API WRAPPERS
# ================================

def api_get(path: str, params: dict | None = None):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict):
    url = f"{API_BASE}{path}"
    resp = requests.post(url, json=body)
    resp.raise_for_status()
    return resp.json()


# ================================
# HELPERS PARA TOOLTIP
# ================================

def _title_paciente(p: dict) -> str:
    pid = p.get("code") or p.get("id")
    dept = p.get("department") or p.get("departamento") or "-"
    disease = p.get("disease") or p.get("enfermedad") or "-"
    severity = p.get("severity") or p.get("gravedad") or "-"
    lines = [
        f"<b>Paciente {pid}</b>",
        f"Depto: {dept}",
        f"Enfermedad: {disease}",
        f"Gravedad: {severity}",
    ]
    return "<br>".join(lines)


def _title_hospital(h: dict) -> str:
    hid = h.get("id")
    name = h.get("name") or h.get("nombre") or "-"
    dept = h.get("department") or h.get("departamento") or "-"
    beds = (
        h.get("beds")
        or h.get("capacidad_camas")
        or h.get("Capacidad_Camas")
        or "-"
    )
    uci = h.get("uci_beds") or h.get("camas_uci") or h.get("Camas_UCI") or "-"
    specs = h.get("specialties") or h.get("especialidades") or "-"
    lines = [
        f"<b>Hospital {hid}</b>",
        name,
        f"Depto: {dept}",
        f"Camas: {beds} | UCI: {uci}",
        f"Especialidades: {specs}",
    ]
    return "<br>".join(lines)


# ================================
# PYVIS — GRAFO INTERACTIVO
# ================================

def draw_graph(patients, hospitals, edges, title: str, max_edges: int = 8000):
    """
    Dibuja un grafo interactivo usando PyVis.
    - Pacientes: nodos grises pequeños.
    - Hospitales: nodos de color (por departamento) más grandes.
    - Aristas: color del hospital al que conectan.
    - max_edges: máximo de aristas a visualizar (para no saturar la vista).
    """

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#FFFFFF",
        font_color="black",
        notebook=False,
    )
    net.force_atlas_2based(gravity=-50)
    net.heading = title

    # --- Colores por departamento de hospital ---
    base_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf",
    ]
    dept_color_map: dict[str, str] = {}
    hospital_color_map: dict[str, str] = {}

    # Hospitales
    for h in hospitals:
        hid = h.get("id")
        dept = h.get("department") or h.get("departamento") or "Hospital"

        if dept not in dept_color_map:
            dept_color_map[dept] = base_colors[len(dept_color_map) % len(base_colors)]
        color = dept_color_map[dept]
        hospital_color_map[hid] = color

        net.add_node(
            hid,
            label=str(hid),
            title=_title_hospital(h),
            color=color,
            shape="square",
            size=22,        # 🔹 más grande
            borderWidth=3,  # 🔹 borde marcado
            group=dept,
        )

    # Pacientes
    for p in patients:
        pid = p.get("id")
        net.add_node(
            pid,
            label=str(pid),
            title=_title_paciente(p),
            color="#555555",
            shape="dot",
            size=6,          # 🔹 más pequeño
            group="Paciente",
        )

    # --- Limitar número de aristas para visualización ---
    total_edges = len(edges)
    if total_edges > max_edges:
        edges_to_draw = random.sample(edges, max_edges)
        st.info(
            f"Se muestran {max_edges} de {total_edges} aristas para una mejor visualización."
        )
    else:
        edges_to_draw = edges

    # Aristas
    for e in edges_to_draw:
        s = e.get("source")
        t = e.get("target")
        dist = e.get("weight") or e.get("distance_km") or e.get("dist_km")

        # color = color del hospital si está en el grafo
        hosp_id = t if t in hospital_color_map else (s if s in hospital_color_map else None)
        edge_color = hospital_color_map.get(hosp_id, "#CCCCCC")

        title_edge = None
        if dist is not None:
            try:
                title_edge = f"Distancia: {float(dist):.2f} km"
            except Exception:
                title_edge = f"Distancia: {dist}"

        net.add_edge(
            s,
            t,
            color=edge_color,
            width=1,
            title=title_edge,
            physics=True,
        )

    # Generar HTML en memoria
    html_str = net.generate_html(notebook=False)
    components.html(html_str, height=800, scrolling=True)

    st.caption(
        "Pacientes = gris • Hospitales = colores por departamento • "
        "Aristas = color del hospital (usa zoom/drag y hover para detalles)."
    )


# ================================
# MAIN UI
# ================================

def show_backend_dashboard():
    st.title("Panel de algoritmos y grafos (Backend Flask)")

    st.markdown("""
        ### Funcionalidades:
        - Visualizar grafos **KNN**, **Radio** y **Bipartito**.
        - Ver métricas de construcción de grafo.
        - Elegir un paciente y calcular su **mejor hospital**.
        - Comparar algoritmos: **Greedy**, **Hungarian**, **MCMF**.
    """)

    # ================================
    # 1) GRAFOS
    # ================================
    st.header("1. Selección y visualización de grafo")

    mode = st.selectbox(
        "Tipo de grafo",
        options=["bipartite_knn", "knn", "radius"],
        format_func=lambda m: {
            "knn": "KNN geográfico",
            "radius": "Por radio (ε-vecindario)",
            "bipartite_knn": "Bipartito paciente → hospital",
        }[m],
    )

    k = None
    radius_km = None

    if mode in ("knn", "bipartite_knn"):
        k = st.number_input("k (para KNN y bipartito)", 1, 50, 10)

    if mode == "radius":
        radius_km = st.number_input("Radio (km)", 1.0, 500.0, 50.0)

    # 🔹 Slider para controlar cuántas aristas se dibujan
    edge_limit = st.slider(
        "Máximo de aristas a visualizar",
        min_value=1000,
        max_value=30000,
        value=8000,
        step=1000,
    )

    if st.button("Generar grafo", type="primary"):
        if mode == "knn":
            data = api_get("/graph/knn", params={"k": int(k)})
            title = f"Grafo KNN (k={k})"
        elif mode == "radius":
            data = api_get("/graph/radius", params={"radius": float(radius_km)})
            title = f"Grafo por radio R={radius_km} km"
        else:  # bipartito
            data = api_get("/graph/bipartite", params={"k": int(k)})
            title = f"Grafo bipartito paciente → hospital (k={k})"

        patients = data.get("patients", [])
        hospitals = data.get("hospitals", [])
        edges = data.get("edges", [])

        st.success(
            f"Grafo generado: {len(patients)} pacientes, "
            f"{len(hospitals)} hospitales, {len(edges)} aristas."
        )
        draw_graph(patients, hospitals, edges, title, max_edges=int(edge_limit))

    # ================================
    # 2) COMPARACIÓN DE GRAFOS
    # ================================
    st.subheader("Comparación de constructores")

    col1, col2 = st.columns(2)
    k_cmp = col1.number_input("k comparación", 1, 50, 10)
    radius_cmp = col2.number_input("Radio comparación", 1.0, 500.0, 50.0)

    if st.button("Comparar métodos"):
        cmp_data = api_get(
            "/graph/compare",
            params={"k": int(k_cmp), "radius": float(radius_cmp)},
        )
        graphs = cmp_data.get("graphs", [])
        if graphs:
            st.dataframe(pd.DataFrame(graphs))
            st.markdown("""
            - `time_ms`: tiempo de construcción.
            - `num_edges`: número de aristas.
            - `avg_degree`: grado promedio (densidad).
            """)
        else:
            st.warning("No se recibieron datos.")

    st.markdown("---")

    # ================================
    # 3) ASIGNACIÓN DE PACIENTES
    # ================================
    st.header("2. Asignación de pacientes")

    try:
        patients_list = api_get("/patients")
    except Exception as e:
        st.error(f"No se pudo obtener /patients: {e}")
        return

    if not patients_list:
        st.warning("No hay pacientes disponibles.")
        return

    options = [
        f"{p.get('code')} - {p.get('department')} - {p.get('disease')}"
        for p in patients_list
    ]
    codes = [p.get("code") for p in patients_list]

    selected = st.selectbox("Selecciona un paciente", options)
    selected_code = codes[options.index(selected)]

    colA, colB = st.columns(2)

    with colA:
        st.subheader("Asignación final (patient-best)")
        if st.button("Calcular asignación", key="btn_best"):
            try:
                best = api_post("/assign/patient-best", {"patient_code": selected_code})
                st.json(best)
            except Exception as e:
                st.error(f"Error /assign/patient-best: {e}")

    with colB:
        st.subheader("Comparación de algoritmos")
        if st.button("Comparar (Greedy / Hungarian / MCMF)", key="btn_compare"):
            try:
                cmp = api_post(
                    "/assign/compare-patient", {"patient_code": selected_code}
                )
                algos = cmp.get("assignment_algorithms", [])
                if algos:
                    df = pd.DataFrame(algos)
                    df = df.drop(columns=["hospital", "paths"], errors="ignore")
                    st.dataframe(df)
                else:
                    st.warning("Sin datos.")
            except Exception as e:
                st.error(f"Error /assign/compare-patient: {e}")
