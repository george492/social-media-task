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
        # Standardise column names (lowercase, strip whitespace)
        nodes_df = nodes_df.copy()
        nodes_df.columns = nodes_df.columns.str.strip().str.lower()
        
        # Map common synonyms → id
        if "id" not in nodes_df.columns:
            for syn in ["node_id", "node", "name", "user", "account", "userid"]:
                if syn in nodes_df.columns:
                    nodes_df.rename(columns={syn: "id"}, inplace=True)
                    break
                    
        if "id" not in nodes_df.columns:
            raise ValueError(f"Nodes CSV must contain an 'id' column. Found columns: {list(nodes_df.columns)}")

        # Map common synonyms → group (for NMI ground truth)
        if "group" not in nodes_df.columns:
            for syn in ["class", "community", "cluster", "label", "category", "dept", "department"]:
                if syn in nodes_df.columns:
                    nodes_df.rename(columns={syn: "group"}, inplace=True)
                    break

        records = nodes_df.to_dict("records")
        for row in records:
            node_id = str(row["id"])
            attrs = {k: v for k, v in row.items() if k != "id"}
            # Provide default label if missing
            if "label" not in attrs:
                attrs["label"] = node_id
            G.add_node(node_id, **attrs)

    # --- Add edges ---
    if edges_df is not None and not edges_df.empty:
        # Standardise column names
        edges_df = edges_df.copy()
        edges_df.columns = edges_df.columns.str.strip().str.lower()
        
        # Map common synonyms → source / target
        src_syns = ["from", "src", "node1", "node_1", "source_id", "from_id"]
        tgt_syns = ["to", "tgt", "node2", "node_2", "target_id", "to_id"]
        if "source" not in edges_df.columns:
            for syn in src_syns:
                if syn in edges_df.columns:
                    edges_df.rename(columns={syn: "source"}, inplace=True)
                    break
        if "target" not in edges_df.columns:
            for syn in tgt_syns:
                if syn in edges_df.columns:
                    edges_df.rename(columns={syn: "target"}, inplace=True)
                    break
            
        for col in ["source", "target"]:
            if col not in edges_df.columns:
                raise ValueError(f"Edges CSV must contain a '{col}' column. Found columns: {list(edges_df.columns)}")

        records = edges_df.to_dict("records")
        for row in records:
            src = str(row["source"])
            tgt = str(row["target"])
            weight = float(row.get("weight", 1.0)) if "weight" in row else 1.0
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
