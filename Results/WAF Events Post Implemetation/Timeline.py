import matplotlib.pyplot as plt
import json
from collections import defaultdict

files = [
    "firewall-events-2026-03-19T23_16_57Z-2026-03-20T23_16_57Z.json",
    "firewall-events-2026-03-20T13_24_08Z-2026-03-21T13_24_08Z.json",
    "firewall-events-2026-03-21T08_05_17Z-2026-03-22T08_05_17Z.json",
]

hourly = defaultdict(int)
for f in files:
    with open(f) as fp:
        for e in json.load(fp):
            hourly[e['datetime'][:13]] += 1

hours  = sorted(hourly)
counts = [hourly[h] for h in hours]
labels = [h[5:] for h in hours]  # strip year

fig, ax = plt.subplots(figsize=(14, 4))
ax.bar(range(len(hours)), counts, color='#e05c5c')
ax.set_xticks(range(len(hours)))
ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
ax.set_ylabel("Events")
ax.set_title("Hourly WAF Rule Events — 19–22 March 2026")
ax.axhline(y=50, color='grey', linestyle='--', alpha=0.4, label='50 event threshold')
plt.tight_layout()
plt.savefig("waf_timeline.png", dpi=150)
print("Saved waf_timeline.png")