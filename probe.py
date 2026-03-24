"""
probe.py  –  Enhanced traceroute probe
  • Sends 5 probes per hop (was 3) for better RTT statistics
  • Does NOT skip private / RFC-1918 addresses
  • Falls back to UDP if ICMP gets no reply (helps cross firewalls)
  • Records packet loss % per hop
  • Saves rich data to hops.txt
"""

from scapy.all import IP, ICMP, UDP, sr1
import time
import ipaddress

# ── configuration ──────────────────────────────────────────────────────────────
DEST        = "1.1.1.1"
MAX_HOPS    = 30
PROBES      = 5          # probes per hop  (was 3)
TIMEOUT     = 2          # seconds
UDP_DPORT   = 33434      # classic traceroute UDP port
# ──────────────────────────────────────────────────────────────────────────────


def is_private(ip_str):
    """Return True for RFC-1918 / link-local addresses (we still include them)."""
    try:
        return ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return False


def probe_hop(ttl):
    """
    Send PROBES ICMP packets at the given TTL.
    If all ICMP probes time out, retry with UDP (helps bypass some firewalls).
    Returns (hop_ip, rtts, loss_pct, proto_used)
    """
    hop_ip = None
    rtts   = []
    proto  = "ICMP"

    # ── ICMP probes ────────────────────────────────────────────────────────────
    for _ in range(PROBES):
        pkt   = IP(dst=DEST, ttl=ttl) / ICMP()
        start = time.time()
        reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
        rtt   = (time.time() - start) * 1000

        if reply is None:
            rtts.append(None)
        else:
            rtts.append(round(rtt, 3))
            hop_ip = reply.src

    # ── UDP fallback if every ICMP probe timed out ─────────────────────────────
    if all(r is None for r in rtts):
        proto  = "UDP"
        rtts   = []
        for i in range(PROBES):
            pkt   = IP(dst=DEST, ttl=ttl) / UDP(dport=UDP_DPORT + i)
            start = time.time()
            reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
            rtt   = (time.time() - start) * 1000

            if reply is None:
                rtts.append(None)
            else:
                rtts.append(round(rtt, 3))
                hop_ip = reply.src

    valid      = [r for r in rtts if r is not None]
    loss_pct   = round((rtts.count(None) / PROBES) * 100, 1)

    return hop_ip, rtts, loss_pct, proto


# ── main loop ─────────────────────────────────────────────────────────────────
hops = []

print(f"Tracing route to {DEST}  ({PROBES} probes/hop, max {MAX_HOPS} hops)\n")
print(f"{'Hop':>4}  {'IP':<20}  {'Avg RTT':>9}  {'Min':>9}  {'Max':>9}  {'Loss':>6}  Proto  Private")
print("-" * 82)

for ttl in range(1, MAX_HOPS + 1):
    hop_ip, rtts, loss_pct, proto = probe_hop(ttl)

    valid = [r for r in rtts if r is not None]
    avg   = round(sum(valid) / len(valid), 3) if valid else None
    mn    = round(min(valid), 3)               if valid else None
    mx    = round(max(valid), 3)               if valid else None

    priv  = is_private(hop_ip) if hop_ip else False
    label = hop_ip if hop_ip else "*"

    print(f"{ttl:>4}  {label:<20}  "
          f"{str(avg)+' ms':>9}  {str(mn)+' ms':>9}  {str(mx)+' ms':>9}  "
          f"{loss_pct:>5}%  {proto:<5}  {'yes' if priv else 'no'}")

    # store full record  (ttl, ip, rtts, loss_pct, proto)
    hops.append((ttl, hop_ip, rtts, loss_pct, proto))

    if hop_ip == DEST:
        print("\nReached destination.")
        break

# ── save ──────────────────────────────────────────────────────────────────────
with open("hops.txt", "w") as f:
    for h in hops:
        f.write(str(h) + "\n")

print("\nSaved to hops.txt")
