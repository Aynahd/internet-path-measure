# Traceroute Analyser

A Python-based network diagnostics toolkit that sends ICMP/UDP probes, geolocates every hop (including private IPs), and produces rich visualisations with ML-based anomaly detection.

---

<img width="2029" height="1090" alt="image" src="https://github.com/user-attachments/assets/46c852c0-310a-4fda-854d-59ba70ba8d04" />
<img width="2198" height="663" alt="Screenshot from 2026-03-25 02-03-19" src="https://github.com/user-attachments/assets/d2079f39-0d89-4f59-b9a5-029bea8731a4" />


## Files

| File | Purpose |
|------|---------|
| `probe.py` | Send traceroute probes and save raw data to `hops.txt` |
| `graph.py` | RTT line chart with error bands, packet-loss overlay, anomaly markers |
| `topo.py` | NetworkX topology graph colour-coded by hop health |
| `geo.py` | Geo-lookup every hop; private IPs resolved via reverse DNS |
| `map.py` | Interactive Folium map with animated path and rich popups |
| `ml.py` | K-Means + Isolation Forest + bottleneck scoring report |
| `dashboard.py` | Single-page matplotlib dashboard combining all panels |

---

## Quick Start

### 1. Install dependencies
```
pip install scapy requests folium scikit-learn numpy matplotlib
```

### 2. Run the probe (needs root / admin for raw sockets)
```
sudo python probe.py
```
This writes `hops.txt`.

### 3. Generate all outputs
```
python graph.py        # → graph.png
python topo.py         # → topology.png
python geo.py          # → geo_results.txt
python map.py          # → map.html  (open in browser)
python ml.py           # → console report
python dashboard.py    # → dashboard.png
python rtt_heatmap.py  # → rtt_heatmap.png  (runs 5 live passes)
```

---

## Key Improvements Over Original

### More probes
- **5 probes per hop** (was 3) → better average RTT and min/max statistics.
- UDP fallback when ICMP times out → crosses more firewalls.

### Private / RFC-1918 IPs included
- Hops behind NAT or LAN routers are **no longer skipped**.
- They appear in green on the topology graph and map.
- Reverse-DNS lookup provides a hostname label when available.

### ML Analysis (`ml.py`)
| Technique | What it detects |
|-----------|-----------------|
| **K-Means (3 clusters)** | Groups hops into Low / Medium / High latency |
| **Isolation Forest** | Flags statistically unusual hops (outliers) |
| **IQR outlier rule** | Secondary anomaly check shown in `graph.py` |
| **Δ RTT bottleneck score** | Finds hops where latency jumps sharply |
| **Jitter metric** | Std-dev of RTT samples per hop |

### Richer visualisations
- `graph.py` – min/max shading, twin-axis packet-loss bars, anomaly stars.
- `topo.py` – left-to-right layout, edge width = RTT, colour = health.
- `map.py` – animated AntPath, per-segment colour, detailed popups, legend.
- `dashboard.py` – 6-panel single image combining RTT, loss, scatter, pie, delta, table.
- `rtt_heatmap.py` – NEW: runs multiple passes and plots a hop × run heatmap.

---

## hops.txt format

Each line is a Python tuple:
```
(ttl, ip_or_None, [rtt1, rtt2, rtt3, rtt4, rtt5], loss_pct, proto)
```
Example:
```
(1, '192.168.1.1', [1.23, 1.45, None, 1.31, 1.28], 20.0, 'ICMP')
```
