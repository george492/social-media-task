"""
community.py
------------
Community detection algorithms using Girvan-Newman and Louvain methods.
Provides comparison utilities and modularity computation.
"""

import networkx as nx
import networkx.algorithms.community as nx_comm
from typing import Dict, List, Optional, Set, Any

try:
    import community as louvain_pkg  # python-louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False
    print("[community] python-louvain not available; Louvain will fall back to greedy modularity.")


def _sanitize_weights(G: nx.Graph) -> nx.Graph:
    """
    Return a copy of G with:
    - All nodes relabelled as strings (for consistent ID handling)
    - All edge 'weight' attributes cast to float.
    """
    H = nx.relabel_nodes(G, {n: str(n) for n in G.nodes()})
    for u, v, data in H.edges(data=True):
        if "weight" in data:
            try:
                H[u][v]["weight"] = float(str(data["weight"]))
            except (ValueError, TypeError):
                H[u][v]["weight"] = 1.0
    return H


def _compute_ebc(G: nx.Graph) -> Dict[tuple, float]:
    """
    Computes edge betweenness centrality manually using Brandes' algorithm:
    - BFS from each node to count shortest paths.
    - Propagate edge credit from leaf nodes upward.
    - Divide by 2 for undirected graphs.
    """
    betweenness = {tuple(sorted((u, v))): 0.0 for u, v in G.edges()}
    nodes = list(G.nodes())
    
    for s in nodes:
        S = []
        P = {v: [] for v in nodes}
        sigma = {v: 0.0 for v in nodes}
        sigma[s] = 1.0
        d = {v: -1 for v in nodes}
        d[s] = 0
        Q = [s]
        
        # Phase 1: BFS
        while Q:
            v = Q.pop(0)
            S.append(v)
            for w in G.neighbors(v):
                if d[w] < 0:
                    Q.append(w)
                    d[w] = d[v] + 1
                if d[w] == d[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
                    
        # Phase 2: Propagate credit from leaf nodes upward
        delta = {v: 0.0 for v in nodes}
        while S:
            w = S.pop()
            for v in P[w]:
                if sigma[w] != 0:
                    c = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                    edge = tuple(sorted((v, w)))
                    betweenness[edge] += c
                    delta[v] += c
                
    # Phase 3: Undirected graph -> divide final betweenness values by 2
    for e in betweenness:
        betweenness[e] /= 2.0
        
    return betweenness


def detect_girvan_newman(G: nx.Graph, num_communities: Optional[int] = None) -> Dict[str, Any]:
    """
    Detect communities using the Girvan-Newman algorithm.
    Runs iteratively, removing the highest edge-betweenness edge one at a time.
    Stops when the desired number of communities is reached, or no edges remain.
    """
    if G is None or G.number_of_nodes() == 0:
        return {"target_communities": []}

    base = G.to_undirected() if G.is_directed() else G
    H = _sanitize_weights(base)
    
    components = [set(c) for c in nx.connected_components(H)]
    
    component_ebc = {}
    for comp in components:
        if len(comp) > 1:
            component_ebc[frozenset(comp)] = _compute_ebc(H.subgraph(comp))
            
    while H.number_of_edges() > 0:
        # Stop condition: desired number of communities is reached
        if num_communities is not None and len(components) >= num_communities:
            break
            
        # Identify the edge with the highest betweenness
        max_edge = None
        max_val = -1.0
        max_comp = None
        
        for comp, ebc_dict in component_ebc.items():
            for e, val in ebc_dict.items():
                if val > max_val:
                    max_val = val
                    max_edge = e
                    max_comp = comp
                    
        if max_edge is None:
            break
            
        # Remove the edge with the highest betweenness
        H.remove_edge(*max_edge)
        
        # Find new components for the affected component
        affected_subgraph = H.subgraph(max_comp)
        new_comps = [set(c) for c in nx.connected_components(affected_subgraph)]
        
        # Update components list
        components = [c for c in components if c != max_comp] + new_comps
        
        # Recalculate betweenness for affected edges (the new components)
        del component_ebc[frozenset(max_comp)]
        for nc in new_comps:
            if len(nc) > 1:
                component_ebc[frozenset(nc)] = _compute_ebc(H.subgraph(nc))
                
    return {"target_communities": components}


def detect_louvain(G: nx.Graph) -> Dict[str, int]:
    """
    Detect communities using the Louvain algorithm.
    Falls back to greedy modularity if python-louvain is not installed.
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)  # nodes are now strings

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
    """
    mapping = {}
    for cid, community in enumerate(communities):
        for node in community:
            mapping[str(node)] = cid
    return mapping


def compute_modularity(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute the modularity score for a given partition.
    """
    if G is None or G.number_of_nodes() == 0 or not partition:
        return 0.0

    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)  # nodes are strings after this

    community_ids = set(partition.values())
    communities = [
        {str(n) for n, c in partition.items() if c == cid}
        for cid in community_ids
    ]
    graph_nodes = set(base.nodes())
    communities = [c & graph_nodes for c in communities]
    communities = [c for c in communities if c]

    try:
        val = round(nx_comm.modularity(base, communities), 4)
        return 0.0 if val == -0.0 else val
    except Exception as e:
        print(f"[community] Modularity computation failed: {e}")
        return 0.0


def compare_algorithms(G: nx.Graph, gn_k: int = 4, algo: str = "both") -> Dict[str, Any]:
    """
    Run both Girvan-Newman and Louvain algorithms and return comparison metrics.
    """
    results = {}

    # Girvan-Newman
    if algo in ["girvan_newman", "both"]:
        target_k = int(gn_k) if gn_k and int(gn_k) > 0 else None
        gn_result = detect_girvan_newman(G, num_communities=target_k)
        gn_communities = gn_result["target_communities"]
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
