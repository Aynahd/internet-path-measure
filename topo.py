"""
topo.py  –  Enhanced network-path topology graph
  • Edge width proportional to average RTT
  • Node colour: green = private IP, red = anomaly, orange = high loss,
                 blue = normal
  • Packet-loss % shown as edge label
  • Uses a left-to-right hierarchical layout (not random spring)
  • Private-IP hops are included and clearly distinguished
"""

import ast
import ipaddress
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── load ──────────────────────────────────────────────────────────────────────
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

# ── helpers ───────────────────────────────────────────────────────────────────
def is_private(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except Exception:
        return False

def avg_rtt(rtts):
    v = [r for r in rtts if r is not None]
    return round(sum(v) / len(v), 2) if v else None

# ── anomaly detection (IQR) ───────────────────────────────────────────────────
all_avgs = []
for rec in hops:
    a = avg_rtt(rec[2])
    all_avgs.append(a if a is not None else 0)

arr = np.array(all_avgs)
Q1, Q3 = np.percentile(arr[arr > 0], [25, 75])
IQR = Q3 - Q1
hi_thresh = Q3 + 1.5 * IQR

# ── build graph ───────────────────────────────────────────────────────────────
G   = nx.DiGraph()
prev = "Your PC"
G.add_node(prev)

node_colors = {"Your PC": "dodgerblue"}
node_labels = {}

for rec in hops:
    ttl   = rec[0]
    ip    = rec[1]
    rtts  = rec[2]
    loss  = rec[3] if len(rec) > 3 else 0

    node  = ip if ip else f"unknown_{ttl}"
    rtt_v = avg_rtt(rtts)

    G.add_node(node)

    # colour logic
    if ip and is_private(ip):
        color = "limegreen"
    elif rtt_v and rtt_v > hi_thresh:
        color = "tomato"          # anomaly / bottleneck
    elif loss and loss >= 50:
        color = "orange"          # high packet loss
    else:
        color = "steelblue"

    node_colors[node] = color

    # edge with RTT weight
    edge_w = max(1, (rtt_v or 0) / 20)   # scale for display
    G.add_edge(prev, node,
               weight=edge_w,
               rtt=rtt_v,
               loss=loss)

    node_labels[node] = f"{node}\n{rtt_v} ms" if rtt_v else node
    prev = node

node_labels["Your PC"] = "Your PC"

# ── hierarchical left-to-right layout ─────────────────────────────────────────
pos = {}
nodes_list = list(nx.topological_sort(G))
for i, n in enumerate(nodes_list):
    pos[n] = (i * 2.0, 0)          # straight horizontal line

# ── draw ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(max(14, len(G.nodes) * 2), 6))

colors = [node_colors.get(n, "steelblue") for n in G.nodes()]
edges  = G.edges(data=True)
widths = [d.get("weight", 1) for _, _, d in edges]

nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=1800, ax=ax)
nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=7, ax=ax)
nx.draw_networkx_edges(G, pos, width=widths, edge_color="grey",
                       arrows=True, arrowsize=20,
                       connectionstyle="arc3,rad=0.1", ax=ax)

# edge labels: packet loss
edge_loss_labels = {(u, v): f"{d['loss']}% loss"
                    for u, v, d in G.edges(data=True)
                    if d.get("loss", 0) > 0}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_loss_labels,
                             font_size=6, ax=ax)

# legend
legend_patches = [
    mpatches.Patch(color="dodgerblue", label="Source (Your PC)"),
    mpatches.Patch(color="limegreen",  label="Private IP"),
    mpatches.Patch(color="steelblue",  label="Normal hop"),
    mpatches.Patch(color="tomato",     label="Anomaly / bottleneck (high RTT)"),
    mpatches.Patch(color="orange",     label="High packet loss (≥50 %)"),
]
ax.legend(handles=legend_patches, loc="upper left", fontsize=8)

ax.set_title("Network Path Topology  –  RTT-weighted, colour-coded by hop health",
             fontsize=12, fontweight="bold")
ax.axis("off")
plt.tight_layout()
plt.savefig("topology.png", dpi=150, bbox_inches="tight")
print("Saved topology.png")
