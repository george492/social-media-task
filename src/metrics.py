"""
metrics.py
----------
Graph metrics and statistical computations using NetworkX.
Computes degree distribution, clustering coefficients, centrality measures,
and average path lengths for both directed and undirected graphs.
"""

import networkx as nx
import numpy as np
from typing import Dict, Any, List, Tuple


def compute_degree_distribution(G: nx.Graph) -> Dict[int, int]:
    """
    Compute the degree distribution of the graph.

    Args:
        G: A NetworkX graph.

    Returns:
        Dict mapping degree value -> count of nodes with that degree.
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    degree_sequence = [d for _, d in G.degree()]
    distribution = {}
    for deg in degree_sequence:
        distribution[deg] = distribution.get(deg, 0) + 1
    return dict(sorted(distribution.items()))


def compute_clustering_coefficient(G: nx.Graph) -> float:
    """
    Compute the average clustering coefficient of the graph.

    Args:
        G: A NetworkX graph.

    Returns:
        Average clustering coefficient (float between 0 and 1).
    """
    if G is None or G.number_of_nodes() == 0:
        return 0.0
    # Use undirected version for clustering
    base = G.to_undirected() if G.is_directed() else G
    return nx.average_clustering(base)


def compute_average_path_length(G: nx.Graph) -> float:
    """
    Compute the average shortest path length of the graph.
    For disconnected graphs, computes the average over the largest connected component.

    Args:
        G: A NetworkX graph.

    Returns:
        Average path length (float). Returns 0.0 if graph has < 2 nodes.
    """
    if G is None or G.number_of_nodes() < 2:
        return 0.0

    base = G.to_undirected() if G.is_directed() else G

    if nx.is_connected(base):
        return nx.average_shortest_path_length(base)

    # Fall back to largest connected component
    largest_cc = max(nx.connected_components(base), key=len)
    subgraph = base.subgraph(largest_cc)
    if subgraph.number_of_nodes() < 2:
        return 0.0
        
    # For dense or large graphs, this is extremely slow. Skip or approximate aggressively.
    if subgraph.number_of_nodes() > 200 or subgraph.number_of_edges() > 1000:
        # Approximate by sampling 10 random nodes
        import random
        k_path = min(subgraph.number_of_nodes(), 10)
        sampled_nodes = random.sample(list(subgraph.nodes()), k_path)
        total_length = 0
        paths = 0
        for n in sampled_nodes:
            lengths = nx.single_source_shortest_path_length(subgraph, n)
            total_length += sum(lengths.values())
            paths += len(lengths) - 1 # exclude self
        if paths == 0:
            return 0.0
        return total_length / paths

    return nx.average_shortest_path_length(subgraph)


def compute_centralities(G: nx.Graph) -> Dict[str, Dict[str, float]]:
    """
    Compute multiple centrality measures for all nodes.

    Computes:
        - Degree centrality
        - Betweenness centrality
        - Closeness centrality
        - PageRank

    Args:
        G: A NetworkX graph.

    Returns:
        Nested dict: {node_id: {centrality_name: value}}
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    # Aggressive approximation for dense or large graphs to prevent freezing
    k_approx = min(n_nodes, 10) if (n_nodes > 200 or n_edges > 1000) else None

    degree_c = dict(G.degree())
    betweenness_c = nx.betweenness_centrality(G, k=k_approx, normalized=True)
    
    # Closeness centrality doesn't support k= sampling natively in standard NetworkX
    # For huge graphs, calculate for a tiny sample and default the rest to 0
    if n_nodes > 100:
        import random
        k_closeness = min(n_nodes, 10)
        sampled = random.sample(list(G.nodes()), k_closeness)
        closeness_c = {n: nx.closeness_centrality(G, u=n) for n in sampled}
    else:
        closeness_c = nx.closeness_centrality(G)

    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=500)
    except Exception:
        # Fall back for degenerate graphs
        pagerank = {n: 1.0 / G.number_of_nodes() for n in G.nodes()}

    result = {}
    for node in G.nodes():
        result[str(node)] = {
            "degree": round(degree_c.get(node, 0.0), 6),
            "betweenness": round(betweenness_c.get(node, 0.0), 6),
            "closeness": round(closeness_c.get(node, 0.0), 6),
            "pagerank": round(pagerank.get(node, 0.0), 6),
        }
    return result


def compute_graph_stats(G: nx.Graph) -> Dict[str, Any]:
    """
    Compute a summary of key graph-level statistics.

    Args:
        G: A NetworkX graph.

    Returns:
        Dict with graph-level statistics.
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    degrees = [d for _, d in G.degree()]
    stats = {
        "num_nodes": G.number_of_nodes(),
        "num_edges": G.number_of_edges(),
        "avg_degree": round(np.mean(degrees), 3),
        "max_degree": max(degrees),
        "min_degree": min(degrees),
        "density": round(nx.density(G), 4),
        "clustering_coefficient": round(compute_clustering_coefficient(G), 4),
        "avg_path_length": round(compute_average_path_length(G), 4),
    }
    return stats


def get_centrality_ranges(centralities: Dict[str, Dict[str, float]]) -> Dict[str, Tuple[float, float]]:
    """
    Compute min/max ranges for each centrality measure across all nodes.

    Args:
        centralities: Output of compute_centralities().

    Returns:
        Dict mapping centrality name -> (min_value, max_value).
    """
    if not centralities:
        return {k: (0.0, 1.0) for k in ("degree", "betweenness", "closeness", "pagerank")}

    ranges = {}
    for metric in ("degree", "betweenness", "closeness", "pagerank"):
        values = [v[metric] for v in centralities.values() if metric in v]
        if values:
            ranges[metric] = (round(min(values), 6), round(max(values), 6))
        else:
            ranges[metric] = (0.0, 1.0)
    return ranges
