"""
community.py
------------
Community detection algorithms using Girvan-Newman and Louvain methods.
Provides comparison utilities and modularity computation.
"""

import networkx as nx
import networkx.algorithms.community as nx_comm
from typing import Dict, List, Set, Any

try:
    import community as louvain_pkg  # python-louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False
    print("[community] python-louvain not available; Louvain will fall back to greedy modularity.")


def _sanitize_weights(G: nx.Graph) -> nx.Graph:
    """
    Return a copy of G with all edge 'weight' attributes cast to float.
    Needed because graphs serialised to JSON store everything as strings.
    """
    H = G.copy()
    for u, v, data in H.edges(data=True):
        if "weight" in data:
            try:
                H[u][v]["weight"] = float(str(data["weight"]))
            except (ValueError, TypeError):
                H[u][v]["weight"] = 1.0
    return H


def detect_girvan_newman(G: nx.Graph, num_communities: int = 4) -> List[Set]:
    """
    Detect communities using the Girvan-Newman algorithm (edge betweenness removal).

    Args:
        G: A NetworkX graph (directed or undirected).
        num_communities: Target number of communities to extract.

    Returns:
        List of sets, each set containing node IDs in that community.
    """
    if G is None or G.number_of_nodes() == 0:
        return []

    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)

    # Remove isolated nodes for algorithm stability
    active = base.copy()
    isolated = list(nx.isolates(active))
    active.remove_nodes_from(isolated)

    if active.number_of_nodes() < 2:
        return [set(G.nodes())]

    communities_generator = nx_comm.girvan_newman(active)
    target = min(num_communities, active.number_of_nodes())

    result = None
    for communities in communities_generator:
        result = list(communities)
        if len(result) >= target:
            break

    if result is None:
        result = [set(active.nodes())]

    # Re-add isolated nodes as singleton communities
    for node in isolated:
        result.append({node})

    return result


def detect_louvain(G: nx.Graph) -> Dict[str, int]:
    """
    Detect communities using the Louvain algorithm.
    Falls back to greedy modularity if python-louvain is not installed.

    Args:
        G: A NetworkX graph.

    Returns:
        Dict mapping node_id (str) -> community_id (int).
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)

    if LOUVAIN_AVAILABLE:
        partition = louvain_pkg.best_partition(base)
        return {str(k): int(v) for k, v in partition.items()}

    # Fallback: greedy modularity maximization
    communities = nx_comm.greedy_modularity_communities(base)
    mapping = {}
    for cid, community in enumerate(communities):
        for node in community:
            mapping[str(node)] = cid
    return mapping


def partition_from_list(communities: List[Set]) -> Dict[str, int]:
    """
    Convert a list-of-sets community structure to a node->community_id dict.

    Args:
        communities: List of sets of node IDs.

    Returns:
        Dict mapping node_id (str) -> community integer index.
    """
    mapping = {}
    for cid, community in enumerate(communities):
        for node in community:
            mapping[str(node)] = cid
    return mapping


def compute_modularity(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute the modularity score for a given partition.

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.

    Returns:
        Modularity score (float, typically between -0.5 and 1.0).
    """
    if G is None or G.number_of_nodes() == 0 or not partition:
        return 0.0

    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)

    # Build list-of-sets from partition dict
    community_ids = set(partition.values())
    communities = [
        {n for n, c in partition.items() if c == cid}
        for cid in community_ids
    ]

    try:
        return round(nx_comm.modularity(base, communities), 4)
    except Exception as e:
        print(f"[community] Modularity computation failed: {e}")
        return 0.0


def compare_algorithms(G: nx.Graph, gn_k: int = 4, algo: str = "both") -> Dict[str, Any]:
    """
    Run both Girvan-Newman and Louvain algorithms and return comparison metrics.

    Args:
        G: A NetworkX graph.
        gn_k: Number of communities for Girvan-Newman.
        algo: Which algorithm to run: 'louvain', 'girvan_newman', or 'both'.

    Returns:
        Dict with keys 'girvan_newman' and 'louvain', each containing:
            - num_communities: int
            - modularity: float
            - partition: Dict[str, int]
    """
    results = {}

    # Girvan-Newman - Skip for large dense graphs as it's O(V * E^2) and too slow
    n_edges = G.number_of_edges()
    if algo in ["girvan_newman", "both"] and n_edges <= 1000 and G.number_of_nodes() <= 500:
        gn_communities = detect_girvan_newman(G, num_communities=gn_k)
        gn_partition = partition_from_list(gn_communities)
        gn_modularity = compute_modularity(G, gn_partition)
        results["girvan_newman"] = {
            "num_communities": len(gn_communities),
            "modularity": gn_modularity,
            "partition": gn_partition,
        }
    else:
        results["girvan_newman"] = {
            "num_communities": 0,
            "modularity": 0.0,
            "partition": {}, 
        }

    # Louvain
    if algo in ["louvain", "both"]:
        louvain_partition = detect_louvain(G)
        louvain_num = len(set(louvain_partition.values())) if louvain_partition else 0
        louvain_modularity = compute_modularity(G, louvain_partition)
        results["louvain"] = {
            "num_communities": louvain_num,
            "modularity": louvain_modularity,
            "partition": louvain_partition,
        }
    else:
        results["louvain"] = {
            "num_communities": 0,
            "modularity": 0.0,
            "partition": {},
        }

    return results
