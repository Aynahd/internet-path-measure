"""
geo.py  –  Enhanced geo-location lookup
  • Parses new (ttl, ip, rtts, loss, proto) tuple format from hops.txt
  • Private/RFC-1918 IPs: tries reverse-DNS for a hostname label;
    geo is marked as "LAN / Private" (ip-api won't resolve them)
  • Public IPs: full geo from ip-api.com with caching (no duplicate calls)
  • Outputs a neat table + saves to geo_results.txt
"""

import ast
import socket
import requests
import time

# ── helpers ───────────────────────────────────────────────────────────────────
GEO_URL   = "http://ip-api.com/json/{ip}?fields=country,regionName,city,lat,lon,isp,org,as"
CACHE     = {}          # ip -> geo dict
RATE_WAIT = 0.25        # seconds between api-api calls (free tier: 45/min)

import ipaddress

def is_private(ip_str):
    try:
        return ipaddress.ip_address(ip_str).is_private
    except Exception:
        return False

def reverse_dns(ip_str):
    try:
        return socket.gethostbyaddr(ip_str)[0]
    except Exception:
        return None

def geo_lookup(ip_str):
    if ip_str in CACHE:
        return CACHE[ip_str]

    if is_private(ip_str):
        hostname = reverse_dns(ip_str) or "–"
        result = {
            "country":    "Private/LAN",
            "regionName": "–",
            "city":       "–",
            "lat":        None,
            "lon":        None,
            "isp":        hostname,
            "org":        "RFC-1918",
            "as":         "–",
        }
    else:
        try:
            time.sleep(RATE_WAIT)
            r = requests.get(GEO_URL.format(ip=ip_str), timeout=5)
            result = r.json() if r.status_code == 200 else {}
        except Exception:
            result = {}

    CACHE[ip_str] = result
    return result

# ── load hops ─────────────────────────────────────────────────────────────────
hops = []
with open("hops.txt") as f:
    for line in f:
        line = line.strip()
        if line:
            hops.append(ast.literal_eval(line))

# ── main lookup ───────────────────────────────────────────────────────────────
results = []   # (ttl, ip, geo)

for rec in hops:
    ttl = rec[0]
    ip  = rec[1]

    if ip is None:
        results.append((ttl, f"unknown_{ttl}", None))
        continue

    geo = geo_lookup(ip)
    results.append((ttl, ip, geo))

# ── print table ───────────────────────────────────────────────────────────────
HDR = (f"{'Hop':>4}  {'IP':<20}  {'Country':<18}  {'City':<18}  "
       f"{'Lat':>8}  {'Lon':>9}  {'ISP / rDNS':<30}")
print("\n" + "=" * len(HDR))
print("  GEO-LOCATION RESULTS")
print("=" * len(HDR))
print(HDR)
print("-" * len(HDR))

lines = []
for ttl, ip, geo in results:
    if geo:
        country = geo.get("country") or "–"
        city    = geo.get("city")    or "–"
        lat     = geo.get("lat")     or "–"
        lon     = geo.get("lon")     or "–"
        isp     = geo.get("isp")     or "–"
    else:
        country = city = lat = lon = isp = "–"

    row = f"{ttl:>4}  {ip:<20}  {country:<18}  {city:<18}  {str(lat):>8}  {str(lon):>9}  {isp:<30}"
    print(row)
    lines.append(row)

print("-" * len(HDR))

# ── save ──────────────────────────────────────────────────────────────────────
with open("geo_results.txt", "w") as f:
    f.write(HDR + "\n")
    f.write("-" * len(HDR) + "\n")
    for l in lines:
        f.write(l + "\n")

print("\nSaved geo_results.txt")
