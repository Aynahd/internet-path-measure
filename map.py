"""
map.py  –  Enhanced interactive Folium map
  • Private/RFC-1918 hops shown as green markers (labelled "LAN hop")
  • Path line coloured by RTT health:
      green  = RTT ≤ 50 ms
      orange = RTT 50–150 ms
      red    = RTT > 150 ms  or  packet-loss ≥ 50 %
  • Rich popup: Hop #, IP, RTT avg, jitter, loss %, ISP, city, country
  • Animated AntPath plugin to show traffic direction
  • Legend added to map
"""

import ast
import time
import socket
import ipaddress
import requests
import folium
from folium.plugins import AntPath

# ── helpers ───────────────────────────────────────────────────────────────────
CACHE = {}
RATE_WAIT = 0.25

def is_private(ip_str):
    try:
        return ipaddress.ip_address(ip_str).is_private
    except Exception:
        return False

def reverse_dns(ip_str):
    try:
        return socket.gethostbyaddr(ip_str)[0]
    except Exception:
        return "–"

def geo_lookup(ip_str):
    if ip_str in CACHE:
        return CACHE[ip_str]
    try:
        time.sleep(RATE_WAIT)
        url  = f"http://ip-api.com/json/{ip_str}?fields=country,city,lat,lon,isp,status"
        resp = requests.get(url, timeout=5).json()
        if resp.get("status") == "success":
            CACHE[ip_str] = resp
            return resp
    except Exception:
        pass
    CACHE[ip_str] = {}
    return {}

def avg_rtt(rtts):
    v = [r for r in rtts if r is not None]
    return round(sum(v) / len(v), 2) if v else None

def jitter(rtts):
    import statistics
    v = [r for r in rtts if r is not None]
    return round(statistics.stdev(v), 2) if len(v) > 1 else 0.0

def rtt_color(avg, loss):
    if avg is None or loss >= 50:
        return "red"
    if avg <= 50:
        return "green"
    if avg <= 150:
        return "orange"
    return "red"

# ── load hops ─────────────────────────────────────────────────────────────────
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

# ── build location list ───────────────────────────────────────────────────────
#  Each entry: dict with ttl, ip, lat, lon, avg, jitter, loss, isp, country, city, private
locations = []

# Add source (approximate – use ip-api to find our own public IP)
try:
    my_geo = requests.get("http://ip-api.com/json/", timeout=5).json()
    my_lat, my_lon = my_geo.get("lat", 0), my_geo.get("lon", 0)
    my_city = my_geo.get("city", "Your Location")
except Exception:
    my_lat, my_lon, my_city = 0, 0, "Your Location"

locations.append({
    "ttl": 0, "ip": "Your PC", "lat": my_lat, "lon": my_lon,
    "avg": 0, "jitter": 0, "loss": 0,
    "isp": "–", "country": "–", "city": my_city, "private": False,
    "color": "blue"
})

for rec in hops:
    ttl  = rec[0]
    ip   = rec[1]
    rtts = rec[2]
    loss = rec[3] if len(rec) > 3 else 0

    if ip is None:
        continue

    a  = avg_rtt(rtts)
    j  = jitter(rtts)
    cl = rtt_color(a, loss)

    if is_private(ip):
        # private IP – no geo, show near source
        rdns = reverse_dns(ip)
        loc = {
            "ttl": ttl, "ip": ip,
            "lat": my_lat + ttl * 0.01,   # slight offset so markers don't stack
            "lon": my_lon + ttl * 0.01,
            "avg": a, "jitter": j, "loss": loss,
            "isp": rdns, "country": "Private/LAN", "city": "–",
            "private": True, "color": "green"
        }
    else:
        geo = geo_lookup(ip)
        if not geo.get("lat"):
            continue   # no geo available
        loc = {
            "ttl": ttl, "ip": ip,
            "lat": geo["lat"], "lon": geo["lon"],
            "avg": a, "jitter": j, "loss": loss,
            "isp": geo.get("isp", "–"), "country": geo.get("country", "–"),
            "city": geo.get("city", "–"),
            "private": False, "color": cl
        }

    locations.append(loc)

# ── build map ─────────────────────────────────────────────────────────────────
m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB positron")

for loc in locations:
    icon_color  = "lightblue" if loc["ip"] == "Your PC" else loc["color"]
    icon_symbol = "home" if loc["ip"] == "Your PC" else ("wifi" if loc["private"] else "circle")

    popup_html = f"""
    <b>Hop {loc['ttl']}:  {loc['ip']}</b><br>
    {'<i>(Private/LAN)</i><br>' if loc['private'] else ''}
    Avg RTT : {loc['avg']} ms<br>
    Jitter  : {loc['jitter']} ms<br>
    Loss    : {loc['loss']} %<br>
    ISP     : {loc['isp']}<br>
    City    : {loc['city']}<br>
    Country : {loc['country']}
    """

    folium.Marker(
        location=[loc["lat"], loc["lon"]],
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"Hop {loc['ttl']}: {loc['ip']}",
        icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix="fa")
    ).add_to(m)

# Animated path
coords = [(loc["lat"], loc["lon"]) for loc in locations]
if len(coords) >= 2:
    AntPath(
        locations=coords,
        color="steelblue",
        weight=3,
        opacity=0.8,
        delay=800,
        tooltip="Packet path"
    ).add_to(m)

# Static polyline coloured segment by segment
for i in range(len(locations) - 1):
    a, b = locations[i], locations[i + 1]
    seg_color = b["color"] if b["color"] != "blue" else "steelblue"
    folium.PolyLine(
        [(a["lat"], a["lon"]), (b["lat"], b["lon"])],
        color=seg_color, weight=3, opacity=0.6,
        tooltip=f"Hop {a['ttl']}→{b['ttl']}  avg {b['avg']} ms  loss {b['loss']}%"
    ).add_to(m)

# Legend
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:9999;
     background:white;padding:12px 16px;border-radius:8px;
     box-shadow:2px 2px 6px rgba(0,0,0,.3);font-size:13px;">
  <b>Hop Health</b><br>
  <span style="color:green;">●</span> RTT ≤ 50 ms / Private IP<br>
  <span style="color:orange;">●</span> RTT 50–150 ms<br>
  <span style="color:red;">●</span> RTT > 150 ms or loss ≥ 50 %<br>
  <span style="color:steelblue;">●</span> Source
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

m.save("map.html")
print("Map saved as map.html")
