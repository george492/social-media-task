import sys, time
sys.path.insert(0, '.')
import networkx as nx
from src.community import detect_girvan_newman

# Auto-detect k (no k given — true GN)
G1 = nx.karate_club_graph()
t = time.time()
r1 = detect_girvan_newman(G1)  # no k!
t1 = time.time() - t
print(f"Karate AUTO: {t1:.2f}s  comms={len(r1['optimal_communities'])}  Q={r1['optimal_modularity']:.4f}")

# With k=4 early stop
r2 = detect_girvan_newman(G1, num_communities=4)
print(f"Karate k=4:  {len(r2['optimal_communities'])} comms  Q={r2['optimal_modularity']:.4f}")

# Dense graph auto-detect
G2 = nx.barabasi_albert_graph(300, 27)
t = time.time()
r3 = detect_girvan_newman(G2)
t3 = time.time() - t
print(f"Dense  AUTO: {t3:.2f}s  comms={len(r3['optimal_communities'])}  Q={r3['optimal_modularity']:.4f}")
