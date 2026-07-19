#!/usr/bin/env python3
"""
Renders a language-breakdown pie chart as SVG.
Runs in GitHub Actions; commits assets/languages.svg.

Env:
  GH_TOKEN  - GitHub token (Actions provides GITHUB_TOKEN)
  GH_USER   - username
  EXCLUDE   - comma-separated languages to drop (e.g. "HTML,CSS")
  EXCLUDE_REPOS - comma-separated repo names to drop
"""
import os, json, math, urllib.request, collections

USER      = os.environ.get("GH_USER", "Nathanbijo")
TOKEN     = os.environ["GH_TOKEN"]
EXCLUDE   = {s.strip().lower() for s in os.environ.get("EXCLUDE", "").split(",") if s.strip()}
EX_REPOS  = {s.strip().lower() for s in os.environ.get("EXCLUDE_REPOS", "").split(",") if s.strip()}
TOP_N     = int(os.environ.get("TOP_N", "6"))

QUERY = """
query($login:String!, $cursor:String) {
  user(login:$login) {
    repositories(first:100, after:$cursor, ownerAffiliations:OWNER,
                 isFork:false, orderBy:{field:PUSHED_AT, direction:DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isPrivate
        languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

def gql(cursor=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER, "cursor": cursor}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]["repositories"]

totals = collections.Counter()
colors = {}
cursor = None
while True:
    repos = gql(cursor)
    for repo in repos["nodes"]:
        if repo["name"].lower() in EX_REPOS:
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name.lower() in EXCLUDE:
                continue
            totals[name] += edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    if not repos["pageInfo"]["hasNextPage"]:
        break
    cursor = repos["pageInfo"]["endCursor"]

top = totals.most_common(TOP_N)
other = sum(totals.values()) - sum(v for _, v in top)
if other > 0:
    top.append(("Other", other))
    colors["Other"] = "#4C566A"
grand = sum(v for _, v in top) or 1

# ---------- layout ----------
BG, TXT, MUTED, BORDER = "#0D1117", "#E6EDF3", "#8B98A5", "#233043"
W, H = 470, 250
CX, CY, R, INNER = 128, 132, 88, 46
FONT = "-apple-system,Segoe UI,Helvetica,Arial,sans-serif"

def arc(cx, cy, r, a0, a1):
    x0, y0 = cx + r*math.cos(a0), cy + r*math.sin(a0)
    x1, y1 = cx + r*math.cos(a1), cy + r*math.sin(a1)
    large = 1 if (a1 - a0) > math.pi else 0
    return x0, y0, x1, y1, large

slices, legend = [], []
angle = -math.pi / 2
for i, (name, val) in enumerate(top):
    frac = val / grand
    sweep = frac * 2 * math.pi
    a0, a1 = angle, angle + sweep
    # donut segment
    x0, y0, x1, y1, lg = arc(CX, CY, R, a0, a1)
    ix1, iy1 = CX + INNER*math.cos(a1), CY + INNER*math.sin(a1)
    ix0, iy0 = CX + INNER*math.cos(a0), CY + INNER*math.sin(a0)
    d = (f"M {x0:.2f} {y0:.2f} A {R} {R} 0 {lg} 1 {x1:.2f} {y1:.2f} "
         f"L {ix1:.2f} {iy1:.2f} A {INNER} {INNER} 0 {lg} 0 {ix0:.2f} {iy0:.2f} Z")
    slices.append(
        f'<path d="{d}" fill="{colors[name]}" stroke="{BG}" stroke-width="2">'
        f'<animate attributeName="opacity" from="0" to="1" dur="0.45s" '
        f'begin="{0.09*i:.2f}s" fill="freeze"/></path>'
    )
    # legend
    ly = 46 + i*26
    legend.append(
        f'<rect x="268" y="{ly-9}" width="11" height="11" rx="2.5" fill="{colors[name]}"/>'
        f'<text x="288" y="{ly}" font-family="{FONT}" font-size="13" fill="{TXT}">{name}</text>'
        f'<text x="452" y="{ly}" font-family="{FONT}" font-size="12.5" fill="{MUTED}" '
        f'text-anchor="end">{frac*100:.1f}%</text>'
    )
    angle = a1

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="24" y="32" font-family="{FONT}" font-size="14.5" font-weight="600"
      fill="#88C0D0" letter-spacing="0.6">MOST USED LANGUAGES</text>
<g>{"".join(slices)}</g>
<text x="{CX}" y="{CY-2}" text-anchor="middle" font-family="{FONT}" font-size="19"
      font-weight="700" fill="{TXT}">{len(top)}</text>
<text x="{CX}" y="{CY+16}" text-anchor="middle" font-family="{FONT}" font-size="10.5"
      fill="{MUTED}" letter-spacing="0.8">LANGUAGES</text>
{"".join(legend)}
</svg>'''

os.makedirs("assets", exist_ok=True)
with open("assets/languages.svg", "w") as fh:
    fh.write(svg)
print("wrote assets/languages.svg")
for n, v in top:
    print(f"  {n:<14} {v/grand*100:5.1f}%")
