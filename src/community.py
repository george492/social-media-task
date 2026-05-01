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


def detect_girvan_newman(G: nx.Graph, max_nodes_per_community: Optional[int] = None) -> Dict[str, Any]:
    """
    Detect communities using the Girvan-Newman algorithm.

    How it works:
    - Runs iteratively, removing the highest edge-betweenness edge one at a time.
    - Modularity Q is computed at every split.
    - The partition with the HIGHEST modularity is automatically selected as optimal.

    Optional: pass max_nodes_per_community=k to stop early once the maximum community
              size is <= k.

    For graphs with > 2000 edges, falls back to greedy modularity maximisation.
    """
    _empty = {
        "history": [], "removed_edges": [],
        "optimal_communities": [], "optimal_modularity": 0.0,
        "target_communities": [],
    }

    if G is None or G.number_of_nodes() == 0:
        return _empty

    # ── Density guard ─────────────────────────────────────────────────────────
    base_check = G.to_undirected() if G.is_directed() else G
    if base_check.number_of_edges() > 2000:
        print(f"[Girvan-Newman] Graph too dense ({base_check.number_of_edges()} edges) — "
              f"using greedy modularity maximisation.")
        base_check_str = nx.relabel_nodes(base_check, {n: str(n) for n in base_check.nodes()})
        communities = list(nx_comm.greedy_modularity_communities(base_check_str))
        
        # Enforce max nodes constraint if requested via recursive splitting
        if max_nodes_per_community is not None:
            final_comms = []
            queue = communities.copy()
            while queue:
                c = queue.pop(0)
                if len(c) <= max_nodes_per_community:
                    final_comms.append(c)
                else:
                    sub = base_check_str.subgraph(c)
                    sub_comms = list(nx_comm.greedy_modularity_communities(sub))
                    if len(sub_comms) == 1:
                        # Cannot split further by modularity, chunk arbitrarily
                        nodes = list(sub.nodes())
                        for i in range(0, len(nodes), max_nodes_per_community):
                            final_comms.append(set(nodes[i:i+max_nodes_per_community]))
                    else:
                        queue.extend(sub_comms)
            communities = final_comms

        try:
            mod = round(nx_comm.modularity(base_check_str, communities), 6)
        except Exception:
            mod = 0.0
        return {
            "history": [], "removed_edges": [],
            "optimal_communities": communities,
            "optimal_modularity": mod,
            "target_communities": communities,
        }

    # Always work on an undirected, string-node copy
    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)   # relabels nodes to strings, sanitises weights

    H = base.copy()
    isolated = list(nx.isolates(H))
    H.remove_nodes_from(isolated)

    if H.number_of_edges() == 0:
        comm = [set(base.nodes())]
        return {**_empty, "optimal_communities": comm, "target_communities": comm}

    # ── Inner helpers ─────────────────────────────────────────────────────────

    def _build_partition(comps):
        """List-of-sets including isolated singletons."""
        p = [set(c) for c in comps]
        for iso in isolated:
            p.append({iso})
        return p

    def _modularity(partition):
        try:
            return round(nx_comm.modularity(base, partition), 6)
        except Exception:
            return 0.0

    def _ebc(comp_nodes):
        """Exact unweighted Brandes EBC for one component (Gephi-style)."""
        sub = H.subgraph(comp_nodes).copy()
        n = len(comp_nodes)
        if n > 500:
            return nx.edge_betweenness_centrality(sub, k=min(n, 50), weight=None, normalized=True)
        return nx.edge_betweenness_centrality(sub, weight=None, normalized=True)

    # ── Bootstrap component EBC cache ────────────────────────────────────────
    component_ebc: Dict[frozenset, dict] = {}
    for comp in nx.connected_components(H):
        if len(comp) > 1:
            component_ebc[frozenset(comp)] = _ebc(comp)

    # ── Baseline modularity ───────────────────────────────────────────────────
    init_parts = _build_partition(list(nx.connected_components(H)))
    best_modularity = _modularity(init_parts) if len(init_parts) > 1 else 0.0
    best_partition  = init_parts
    target_partition = init_parts
    reached_target   = False

    history: list       = []
    removed_edges: list = []
    iteration           = 0
    max_removals        = H.number_of_edges()

    # ── Main loop ─────────────────────────────────────────────────────────────
    while iteration < max_removals:

        # Step 1 — find highest EBC edge globally
        top_edge = None
        top_val  = -1.0
        top_comp = None

        for comp, ebc_dict in component_ebc.items():
            if not ebc_dict:
                continue
            e, v = max(ebc_dict.items(), key=lambda x: x[1])
            if v > top_val:
                top_val  = v
                top_edge = e
                top_comp = comp

        if top_edge is None:
            break

        # Step 2 — remove that single edge
        H.remove_edge(*top_edge)
        removed_edges.append(top_edge)
        iteration += 1

        # Step 3 — recalculate EBC only for the affected component
        del component_ebc[top_comp]
        for nc in nx.connected_components(H.subgraph(top_comp)):
            if len(nc) > 1:
                component_ebc[frozenset(nc)] = _ebc(nc)

        # Step 4 — current state
        cur_comps = list(nx.connected_components(H))
        cur_part  = _build_partition(cur_comps)
        num_comms = len(cur_part)
        mod_score = _modularity(cur_part)

        history.append({
            "iteration":       iteration,
            "removed_edge":    top_edge,
            "betweenness":     top_val,
            "num_communities": num_comms,
            "modularity":      mod_score,
        })

        # Step 5 — update best partition
        if mod_score > best_modularity:
            best_modularity = mod_score
            best_partition  = cur_part

        # Step 6 — early stop when max community size is <= k
        if max_nodes_per_community is not None:
            max_size = max(len(c) for c in cur_part) if cur_part else 0
            if max_size <= max_nodes_per_community:
                target_partition = cur_part
                reached_target   = True
                break

        # Also stop if all nodes are isolated
        if num_comms >= H.number_of_nodes() + len(isolated):
            break

    if not reached_target:
        target_partition = best_partition

    print(f"[Girvan-Newman] {iteration} edges removed | "
          f"{len(target_partition)} communities | "
          f"best Q={best_modularity:.4f}")

    return {
        "history":             history,
        "removed_edges":       removed_edges,
        "optimal_communities": best_partition,
        "optimal_modularity":  best_modularity,
        "target_communities":  target_partition,
    }


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
    base = _sanitize_weights(base)  # nodes are strings after this

    # Build list-of-sets using string node IDs
    community_ids = set(partition.values())
    communities = [
        {str(n) for n, c in partition.items() if c == cid}
        for cid in community_ids
    ]
    # Filter out empty sets and ensure all nodes exist in graph
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

    # Girvan-Newman
    n_edges = G.number_of_edges()
    if algo in ["girvan_newman", "both"]:
        # Pass k=None to let the algorithm auto-select the best partition by modularity.
        # If the user set a specific k (gn_k > 0), pass it as an early-stop hint.
        k_hint = int(gn_k) if gn_k and int(gn_k) > 1 else None
        gn_result = detect_girvan_newman(G, max_nodes_per_community=k_hint)
        # We use target_communities to honor the user's max nodes constraint.
        gn_communities = gn_result["target_communities"]
        gn_partition = partition_from_list(gn_communities)
        # Recompute modularity for the target partition
        gn_modularity = compute_modularity(G, gn_partition)
        results["girvan_newman"] = {
            "num_communities": len(gn_communities),
            "modularity": gn_modularity,
            "partition": gn_partition,
            # NOTE: history excluded to keep JSON small
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
