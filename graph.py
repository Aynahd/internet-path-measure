"""
graph.py  –  Enhanced RTT visualisation
  • Error-band (min/max shading) around the average RTT line
  • Packet-loss % shown as a bar chart on a twin axis
  • Anomaly hops (detected by IQR) highlighted in red
  • Private-IP hops marked with a different symbol
"""

import ast
import ipaddress
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── load hops ─────────────────────────────────────────────────────────────────
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

# ── parse ─────────────────────────────────────────────────────────────────────
ttls, avgs, mins, maxs, losses, ips, privates = [], [], [], [], [], [], []

for record in hops:
    ttl  = record[0]
    ip   = record[1]
    rtts = record[2]
    loss = record[3] if len(record) > 3 else None

    valid = [r for r in rtts if r is not None]
    if not valid:
        continue

    avg = sum(valid) / len(valid)
    ttls.append(ttl)
    avgs.append(avg)
    mins.append(min(valid))
    maxs.append(max(valid))
    losses.append(loss if loss is not None else 0)
    ips.append(ip or "unknown")

    try:
        privates.append(ipaddress.ip_address(ip).is_private if ip else False)
    except ValueError:
        privates.append(False)

avgs_np = np.array(avgs)

# ── anomaly detection via IQR ─────────────────────────────────────────────────
Q1, Q3 = np.percentile(avgs_np, 25), np.percentile(avgs_np, 75)
IQR     = Q3 - Q1
anomaly_mask = (avgs_np < Q1 - 1.5 * IQR) | (avgs_np > Q3 + 1.5 * IQR)

# ── plot ──────────────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(13, 6))

# error band
ax1.fill_between(ttls, mins, maxs, alpha=0.2, color="steelblue", label="Min–Max band")

# avg RTT line
ax1.plot(ttls, avgs, marker="o", color="steelblue", lw=2, label="Avg RTT")

# private-IP hops
priv_ttls = [ttls[i] for i in range(len(ttls)) if privates[i]]
priv_avgs = [avgs[i] for i in range(len(ttls)) if privates[i]]
if priv_ttls:
    ax1.scatter(priv_ttls, priv_avgs, marker="s", color="green",
                zorder=5, s=80, label="Private IP hop")

# anomaly hops
anom_ttls = [ttls[i] for i in range(len(ttls)) if anomaly_mask[i]]
anom_avgs = [avgs[i] for i in range(len(ttls)) if anomaly_mask[i]]
if anom_ttls:
    ax1.scatter(anom_ttls, anom_avgs, marker="*", color="red",
                zorder=6, s=180, label="Anomaly (IQR)")
    for tx, ay in zip(anom_ttls, anom_avgs):
        ax1.annotate("anomaly", (tx, ay),
                     textcoords="offset points", xytext=(8, 8),
                     fontsize=8, color="red")

# hop IP labels
for i, (tx, ay, ip) in enumerate(zip(ttls, avgs, ips)):
    ax1.annotate(ip, (tx, ay),
                 textcoords="offset points", xytext=(4, -14),
                 fontsize=6, rotation=30, color="grey")

ax1.set_xlabel("Hop (TTL)", fontsize=11)
ax1.set_ylabel("RTT (ms)", fontsize=11, color="steelblue")
ax1.tick_params(axis="y", labelcolor="steelblue")
ax1.set_xticks(ttls)
ax1.grid(True, linestyle="--", alpha=0.5)

# packet-loss bar on twin axis
ax2 = ax1.twinx()
ax2.bar(ttls, losses, alpha=0.25, color="tomato", width=0.4, label="Packet loss %")
ax2.set_ylabel("Packet Loss (%)", fontsize=11, color="tomato")
ax2.set_ylim(0, 130)
ax2.tick_params(axis="y", labelcolor="tomato")

# legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)

plt.title("RTT vs Hop  –  with Min/Max band, Packet Loss & Anomaly Detection",
          fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig("graph.png", dpi=150)
print("Graph saved as graph.png")
