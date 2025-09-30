# presentation/ui_graph.py
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

from infrastructure.geo_utils import hospitales_cercanos


def show_graph(pacientes_df, hospitales_df):
    st.header("Grafo abstracto: Pacientes ↔ Hospitales (NetworkX)")
    st.markdown("Grafo simplificado — cada paciente conectado a sus 3 hospitales más cercanos (para claridad).")

    sample_n = st.slider(
        "Número de pacientes a mostrar (muestra)",
        min_value=5,
        max_value=min(400, len(pacientes_df)),
        value=min(50, len(pacientes_df)),
    )
    pacientes_muestra = pacientes_df.sample(sample_n, random_state=42).reset_index(drop=True)

    G = nx.Graph()
    for _, p in pacientes_muestra.iterrows():
        G.add_node(p["ID_Paciente"], tipo="paciente")
    for _, h in hospitales_df.iterrows():
        G.add_node(h["ID_Hospital"], tipo="hospital")

    for _, p in pacientes_muestra.iterrows():
        top3 = hospitales_cercanos(p, hospitales_df, top_k=3)
        for _, h in top3.iterrows():
            G.add_edge(p["ID_Paciente"], h["ID_Hospital"])

    fig, ax = plt.subplots(figsize=(12, 9))
    pos = nx.spring_layout(G, seed=42)
    node_colors = ["red" if G.nodes[n].get("tipo") == "paciente" else "blue" for n in G.nodes()]
    nx.draw(G, pos, node_color=node_colors, node_size=60, edge_color="gray", with_labels=False, ax=ax)
    st.pyplot(fig)
    st.markdown("Rojo = Paciente, Azul = Hospital")
