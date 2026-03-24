"""
dashboard.py  –  NEW: single-page analysis dashboard
  Combines into one PNG:
    Panel A – RTT line + error band + anomalies
    Panel B – Packet loss bar chart
    Panel C – Cluster scatter (RTT vs Jitter)
    Panel D – K-Means cluster pie
    Panel E – Hop-by-hop delta RTT (bottleneck view)
    Panel F – Summary stats table
"""

import ast
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ── load ──────────────────────────────────────────────────────────────────────
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

records = []
for rec in hops:
    ttl  = rec[0]
    ip   = rec[1] or f"unknown_{rec[0]}"
    rtts = rec[2]
    loss = rec[3] if len(rec) > 3 else 0

    v = [r for r in rtts if r is not None]
    if not v:
        continue

    avg    = sum(v) / len(v)
    mn, mx = min(v), max(v)
    jitter = float(np.std(v)) if len(v) > 1 else 0.0
    lp     = loss

    records.append({"ttl": ttl, "ip": ip, "avg": avg, "min": mn,
                    "max": mx, "jitter": jitter, "loss": lp})

if len(records) < 3:
    print("Need at least 3 valid hops.")
    exit()

ttls    = [r["ttl"]    for r in records]
avgs    = np.array([r["avg"]    for r in records])
mins    = np.array([r["min"]    for r in records])
maxs    = np.array([r["max"]    for r in records])
jitters = np.array([r["jitter"] for r in records])
losses  = np.array([r["loss"]   for r in records])
ips     = [r["ip"] for r in records]

# ── ML ────────────────────────────────────────────────────────────────────────
X_raw = np.column_stack([avgs, jitters, losses])
sc    = StandardScaler()
X     = sc.fit_transform(X_raw)

km        = KMeans(n_clusters=3, random_state=42, n_init=10)
km_labels = km.fit_predict(X)

iso      = IsolationForest(contamination=0.15, random_state=42)
iso_pred = iso.fit_predict(X)

Q1, Q3 = np.percentile(avgs, 25), np.percentile(avgs, 75)
IQR    = Q3 - Q1
anom_iqr = (avgs > Q3 + 1.5 * IQR) | (avgs < Q1 - 1.5 * IQR)

deltas = np.diff(avgs, prepend=avgs[0])
bn_thr = np.percentile(np.abs(deltas), 75)

# colours per cluster
CMAP   = {0: "steelblue", 1: "darkorange", 2: "mediumseagreen"}
c_sort = np.argsort(km.cluster_centers_[:, 0])   # sort by avg RTT
cnames = {c_sort[0]: "Low", c_sort[1]: "Mid", c_sort[2]: "High"}
node_c = [CMAP[l] for l in km_labels]

# ── layout ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 14))
fig.suptitle("Traceroute Analysis Dashboard", fontsize=16, fontweight="bold", y=0.98)
gs  = gridspec.GridSpec(3, 3, figure=fig, hspace=0.55, wspace=0.4)

axA = fig.add_subplot(gs[0, :2])   # RTT line  (wide)
axB = fig.add_subplot(gs[0,  2])   # loss bar
axC = fig.add_subplot(gs[1, :2])   # scatter RTT vs jitter
axD = fig.add_subplot(gs[1,  2])   # pie
axE = fig.add_subplot(gs[2, :2])   # delta RTT
axF = fig.add_subplot(gs[2,  2])   # table

# ── A: RTT line ───────────────────────────────────────────────────────────────
axA.fill_between(ttls, mins, maxs, alpha=0.15, color="steelblue")
axA.plot(ttls, avgs, "o-", color="steelblue", lw=2, label="Avg RTT")
# anomaly markers
ax_ttls = [ttls[i] for i in range(len(ttls)) if anom_iqr[i]]
ax_avgs = [avgs[i]  for i in range(len(ttls)) if anom_iqr[i]]
if ax_ttls:
    axA.scatter(ax_ttls, ax_avgs, marker="*", color="red", s=200,
                zorder=5, label="Anomaly")
# iso markers
iso_ttls = [ttls[i] for i in range(len(ttls)) if iso_pred[i] == -1]
iso_avgs = [avgs[i]  for i in range(len(ttls)) if iso_pred[i] == -1]
if iso_ttls:
    axA.scatter(iso_ttls, iso_avgs, marker="x", color="purple", s=100,
                zorder=6, linewidths=2, label="IsoForest anomaly")
axA.set_xlabel("Hop"); axA.set_ylabel("RTT (ms)")
axA.set_title("A  –  RTT per Hop (min/avg/max + anomalies)")
axA.set_xticks(ttls)
axA.grid(True, ls="--", alpha=0.4)
axA.legend(fontsize=8)

# ── B: packet loss ────────────────────────────────────────────────────────────
bar_c = ["tomato" if l >= 50 else "salmon" for l in losses]
axB.bar(ttls, losses, color=bar_c)
axB.set_xlabel("Hop"); axB.set_ylabel("Loss (%)")
axB.set_title("B  –  Packet Loss %")
axB.set_xticks(ttls)
axB.set_ylim(0, 110)
axB.axhline(50, color="red", ls="--", lw=1, alpha=0.6)

# ── C: scatter RTT vs Jitter coloured by cluster ─────────────────────────────
for i, (a, j) in enumerate(zip(avgs, jitters)):
    axC.scatter(a, j, color=node_c[i], s=80, zorder=3)
    axC.annotate(f"H{ttls[i]}", (a, j), fontsize=7, xytext=(3, 3),
                 textcoords="offset points")
from matplotlib.lines import Line2D
legend_els = [Line2D([0],[0], marker="o", color="w",
                     markerfacecolor=CMAP[c_sort[k]], markersize=9,
                     label=f"Cluster {k}: {cnames[c_sort[k]]}")
              for k in range(3)]
axC.legend(handles=legend_els, fontsize=8)
axC.set_xlabel("Avg RTT (ms)"); axC.set_ylabel("Jitter (ms)")
axC.set_title("C  –  RTT vs Jitter (coloured by K-Means cluster)")
axC.grid(True, ls="--", alpha=0.4)

# ── D: pie of clusters ────────────────────────────────────────────────────────
unique, counts = np.unique(km_labels, return_counts=True)
pie_labels = [f"{cnames.get(u,'?')} ({counts[i]})" for i, u in enumerate(unique)]
pie_colors = [CMAP[u] for u in unique]
axD.pie(counts, labels=pie_labels, colors=pie_colors,
        autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8})
axD.set_title("D  –  Cluster Distribution")

# ── E: delta RTT (bottleneck) ─────────────────────────────────────────────────
bn_c = ["tomato" if abs(d) > bn_thr else "steelblue" for d in deltas]
axE.bar(ttls, deltas, color=bn_c)
axE.axhline(0, color="black", lw=0.8)
axE.axhline( bn_thr, color="red", ls="--", lw=1, alpha=0.6, label=f"+thresh {bn_thr:.0f}")
axE.axhline(-bn_thr, color="red", ls="--", lw=1, alpha=0.6)
axE.set_xlabel("Hop"); axE.set_ylabel("ΔRTT (ms)")
axE.set_title("E  –  Hop-to-Hop RTT Delta (bottleneck detection)")
axE.set_xticks(ttls)
axE.legend(fontsize=8)
axE.grid(True, ls="--", alpha=0.4)

# ── F: stats table ────────────────────────────────────────────────────────────
axF.axis("off")
col_labels = ["Hop", "IP", "Avg ms", "Loss%", "Cluster", "Anomaly"]
rows = []
for i, rec in enumerate(records):
    rows.append([
        rec["ttl"],
        rec["ip"][:16],
        f"{rec['avg']:.1f}",
        f"{rec['loss']:.0f}",
        cnames.get(km_labels[i], "?"),
        "⚠" if iso_pred[i] == -1 else "–"
    ])
tbl = axF.table(cellText=rows, colLabels=col_labels,
                loc="center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(7.5)
tbl.scale(1, 1.4)
axF.set_title("F  –  Hop Summary", pad=12)

plt.savefig("dashboard.png", dpi=150, bbox_inches="tight")
print("Saved dashboard.png")
