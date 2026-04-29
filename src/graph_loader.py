"""
graph_loader.py
---------------
Handles loading CSV files into NetworkX graph objects.
Supports both directed and undirected graphs with flexible column handling.
"""

import io
import base64
import pandas as pd
import networkx as nx
from typing import Optional, Tuple


def parse_upload(contents: str) -> Optional[pd.DataFrame]:
    """
    Parse a Dash Upload component's base64-encoded file content into a DataFrame.

    Args:
        contents: Base64-encoded file content string from Dash Upload component.

    Returns:
        pd.DataFrame if parsing succeeds, None otherwise.
    """
    if contents is None:
        return None
    try:
        content_type, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)
        return pd.read_csv(io.StringIO(decoded.decode("utf-8")))
    except Exception as e:
        print(f"[graph_loader] Error parsing upload: {e}")
        return None


def load_graph_from_dataframes(
    nodes_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    directed: bool = False,
) -> nx.Graph:
    """
    Build a NetworkX graph from nodes and edges DataFrames.

    Nodes DataFrame expected columns:
        - id (required): unique node identifier
        - label (optional): display label
        - group (optional): cluster/community group integer
        - Any additional columns become node attributes.

    Edges DataFrame expected columns:
        - source (required): source node id
        - target (required): target node id
        - weight (optional, default=1.0): edge weight

    Args:
        nodes_df: DataFrame containing node data.
        edges_df: DataFrame containing edge data.
        directed: If True, creates a DiGraph; otherwise an undirected Graph.

    Returns:
        A NetworkX Graph or DiGraph populated with nodes and edges.
    """
    G = nx.DiGraph() if directed else nx.Graph()

    # --- Add nodes ---
    if nodes_df is not None and not nodes_df.empty:
        if "id" not in nodes_df.columns:
            raise ValueError("Nodes CSV must contain an 'id' column.")

        for _, row in nodes_df.iterrows():
            node_id = str(row["id"])
            attrs = {k: v for k, v in row.items() if k != "id"}
            # Provide default label if missing
            if "label" not in attrs:
                attrs["label"] = node_id
            G.add_node(node_id, **attrs)

    # --- Add edges ---
    if edges_df is not None and not edges_df.empty:
        for col in ["source", "target"]:
            if col not in edges_df.columns:
                raise ValueError(f"Edges CSV must contain a '{col}' column.")

        for _, row in edges_df.iterrows():
            src = str(row["source"])
            tgt = str(row["target"])
            weight = float(row.get("weight", 1.0)) if "weight" in row.index else 1.0
            attrs = {k: v for k, v in row.items() if k not in ("source", "target")}
            attrs["weight"] = weight

            # Auto-add nodes if not present
            if src not in G:
                G.add_node(src, label=src)
            if tgt not in G:
                G.add_node(tgt, label=tgt)

            G.add_edge(src, tgt, **attrs)

    return G


def get_graph_summary(G: nx.Graph) -> dict:
    """
    Return a brief summary dictionary for a given graph.

    Args:
        G: A NetworkX graph.

    Returns:
        Dict with keys: num_nodes, num_edges, is_directed, is_connected.
    """
    if G is None or G.number_of_nodes() == 0:
        return {"num_nodes": 0, "num_edges": 0, "is_directed": False, "is_connected": False}

    base = G.to_undirected() if G.is_directed() else G
    connected = nx.is_connected(base)

    return {
        "num_nodes": G.number_of_nodes(),
        "num_edges": G.number_of_edges(),
        "is_directed": G.is_directed(),
        "is_connected": connected,
    }
