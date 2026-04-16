"""
    1. K-Means clustering  (3 clusters: low / medium / high latency)
    2. Isolation Forest   for unsupervised anomaly detection
    3. Bottleneck scoring  = delta RTT between consecutive hops
    4. Jitter metric       = std-dev of RTT samples per hop
    5. Summary report printed to console
"""

import ast
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

#  load
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

# feature extraction 
records = []    # (ttl, ip, avg_rtt, jitter, loss_pct)

for rec in hops:
    ttl   = rec[0]
    ip    = rec[1]
    rtts  = rec[2]
    loss  = rec[3] if len(rec) > 3 else None

    valid = [r for r in rtts if r is not None]
    if not valid:
        continue

    avg    = sum(valid) / len(valid)
    jitter = float(np.std(valid)) if len(valid) > 1 else 0.0
    lp     = (rtts.count(None) / len(rtts)) * 100 if loss is None else loss

    records.append((ttl, ip or "unknown", round(avg, 3),
                    round(jitter, 3), round(lp, 1)))

if len(records) < 3:
    print("Not enough hops for ML analysis.")
    exit()

ttls    = [r[0] for r in records]
ips     = [r[1] for r in records]
avgs    = np.array([r[2] for r in records])
jitters = np.array([r[3] for r in records])
losses  = np.array([r[4] for r in records])

#  feature matrix 
X_raw = np.column_stack([avgs, jitters, losses])
scaler = StandardScaler()
X = scaler.fit_transform(X_raw)

#  1. K-Means clustering 
n_clusters = min(3, len(records))
km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
km_labels = km.fit_predict(X)

# Map cluster index to human label (sort cluster centres by avg RTT)
centres = km.cluster_centers_
centre_avg = [scaler.inverse_transform([c])[0][0] for c in centres]
sorted_idx = np.argsort(centre_avg)
cluster_names = {sorted_idx[0]: "Low-latency",
                 sorted_idx[1]: "Medium-latency",
                 sorted_idx[2]: "High-latency"}

# 2. Isolation Forest anomaly detection
iso = IsolationForest(contamination=0.15, random_state=42)
iso_pred = iso.fit_predict(X)      # -1 = anomaly, 1 = normal
iso_scores = iso.decision_function(X)   # lower = more anomalous

# 3. Bottleneck scoring: delta RTT between consecutive hops 
deltas = [0.0]
for i in range(1, len(avgs)):
    deltas.append(round(avgs[i] - avgs[i - 1], 3))

bottleneck_thresh = np.percentile([abs(d) for d in deltas], 75)
is_bottleneck = [abs(d) > bottleneck_thresh for d in deltas]

# print report 
HEADER = (f"{'Hop':>4}  {'IP':<20}  {'Avg RTT':>9}  {'Jitter':>8}  "
          f"{'Loss%':>6}  {'Cluster':<16}  {'Anomaly?':>9}  "
          f"{'ΔRTT':>8}  {'Bottleneck?':>12}")
SEP = "-" * len(HEADER)

print("\n" + "=" * len(HEADER))
print("  TRACEROUTE ML ANALYSIS REPORT")
print("=" * len(HEADER))
print(HEADER)
print(SEP)

anomaly_hops     = []
bottleneck_hops  = []

for i, (ttl, ip, avg, jitter, loss) in enumerate(records):
    cname  = cluster_names.get(km_labels[i], "?")
    is_ano = iso_pred[i] == -1
    delta  = deltas[i]
    is_bn  = is_bottleneck[i]

    flag_ano = "YES" if is_ano else "no"
    flag_bn  = "YES" if is_bn  else "no"

    print(f"{ttl:>4}  {ip:<20}  {avg:>7.2f}ms  {jitter:>6.2f}ms  "
          f"{loss:>5.1f}%  {cname:<16}  {flag_ano:>9}  "
          f"{delta:>+7.1f}ms  {flag_bn:>12}")

    if is_ano:
        anomaly_hops.append((ttl, ip, avg))
    if is_bn and i > 0:
        bottleneck_hops.append((ttl, ip, delta))

print(SEP)

# summary
print("\n── SUMMARY ──────────────────────────────────────────────────")
print(f"  Total hops analysed : {len(records)}")
print(f"  Anomalous hops      : {len(anomaly_hops)}")
if anomaly_hops:
    for ttl, ip, avg in anomaly_hops:
        print(f"      Hop {ttl}  {ip}  ({avg:.2f} ms)")

print(f"\n  Bottleneck hops     : {len(bottleneck_hops)}")
if bottleneck_hops:
    for ttl, ip, delta in bottleneck_hops:
        print(f"      Hop {ttl}  {ip}  ΔRTT = {delta:+.1f} ms")

overall_loss = np.mean(losses)
print(f"\n  Average packet loss : {overall_loss:.1f} %")
print(f"  Path jitter (mean)  : {np.mean(jitters):.2f} ms")
print("─────────────────────────────────────────────────────────────\n")
