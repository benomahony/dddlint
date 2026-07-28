import json
import zlib
from collections import Counter, defaultdict
from math import cos, radians, sin

from .config import Config
from .insights import Insight, Point

_COLORS = {
    "global": "#7c3aed",
    "domain": "#2563eb",
    "context": "#0891b2",
    "canonical": "#16a34a",
    "alias": "#374151",
    "forbidden": "#dc2626",
}

_RADII = {
    "global": 38,
    "domain": 32,
    "context": 32,
    "canonical": 22,
    "alias": 16,
    "forbidden": 16,
}


def _build_graph(config: Config) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    def node(id_: str, label: str, kind: str) -> None:
        assert id_, "id_ must be non-empty"
        assert kind in _COLORS, "kind must be a known node type"
        if id_ not in seen:
            nodes.append(
                {"id": id_, "label": label, "type": kind, "color": _COLORS[kind], "r": _RADII[kind]}
            )
            seen.add(id_)

    def edge(src: str, tgt: str, kind: str = "owns") -> None:
        assert src and tgt, "src and tgt must be non-empty"
        assert kind, "kind must be non-empty"
        edges.append({"source": src, "target": tgt, "kind": kind})

    node("global", "Global", "global")

    for term in config.forbidden:
        nid = f"forbidden:{term}"
        node(nid, term, "forbidden")
        edge("global", nid, "forbidden")

    for g in config.synonyms:
        cid = f"canonical:{g.canonical}"
        node(cid, g.canonical, "canonical")
        edge("global", cid, "owns")
        for alias in g.aliases:
            aid = f"alias:{alias}"
            node(aid, alias, "alias")
            edge(aid, cid, "alias")

    for scope_list, kind in [(config.domains, "domain"), (config.contexts, "context")]:
        for scope in scope_list:
            sid = f"{kind}:{scope.name}"
            node(sid, scope.name, kind)
            edge("global", sid, "scope")
            for term in scope.forbidden:
                nid = f"forbidden:{sid}:{term}"
                node(nid, term, "forbidden")
                edge(sid, nid, "forbidden")
            for g in scope.synonyms:
                cid = f"canonical:{sid}:{g.canonical}"
                node(cid, g.canonical, "canonical")
                edge(sid, cid, "owns")
                for alias in g.aliases:
                    aid = f"alias:{sid}:{alias}"
                    node(aid, alias, "alias")
                    edge(aid, cid, "alias")

    assert any(n["type"] == "global" for n in nodes), "graph must contain the global node"
    assert len(seen) == len(nodes), "each node id must be unique"
    return {"nodes": nodes, "edges": edges}


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DDD Graph</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d0f17; overflow: hidden; font-family: system-ui, sans-serif; }}
  canvas {{ display: block; }}
  #legend {{
    position: fixed; bottom: 1.5rem; left: 1.5rem;
    display: flex; gap: 1rem; flex-wrap: wrap;
  }}
  .leg {{ display: flex; align-items: center; gap: 0.35rem;
           font-size: 0.72rem; color: #6b7280; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  #title {{
    position: fixed; top: 1.5rem; left: 1.5rem;
    font-size: 1.1rem; font-weight: 700; color: #e2e4f0;
    letter-spacing: -0.03em;
  }}
  #hint {{
    position: fixed; top: 1.5rem; right: 1.5rem;
    font-size: 0.72rem; color: #374151;
  }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="title">DDD Graph</div>
<div id="hint">scroll to zoom · drag to pan · drag nodes</div>
<div id="legend">
  <div class="leg"><div class="dot" style="background:#7c3aed"></div>global</div>
  <div class="leg"><div class="dot" style="background:#2563eb"></div>domain</div>
  <div class="leg"><div class="dot" style="background:#0891b2"></div>context</div>
  <div class="leg"><div class="dot" style="background:#16a34a"></div>canonical</div>
  <div class="leg"><div class="dot" style="background:#374151;border:1px solid #6b7280"></div>alias</div>
  <div class="leg"><div class="dot" style="background:#dc2626"></div>forbidden</div>
</div>
<script>
const DATA = {data};

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let W, H;

function resize() {{
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}}
resize();
window.addEventListener('resize', resize);

// --- state ---
const nodes = DATA.nodes.map(n => ({{
  ...n,
  x: W/2 + (Math.random()-0.5)*300,
  y: H/2 + (Math.random()-0.5)*300,
  vx: 0, vy: 0, pinned: false
}}));
const edges = DATA.edges;
const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]));

// --- camera ---
let cam = {{ x: 0, y: 0, zoom: 1 }};

// --- interaction ---
let drag = null;
let pan = null;

function worldPos(ex, ey) {{
  return {{
    x: (ex - W/2 - cam.x) / cam.zoom,
    y: (ey - H/2 - cam.y) / cam.zoom,
  }};
}}

function hitNode(wx, wy) {{
  for (let i = nodes.length-1; i >= 0; i--) {{
    const n = nodes[i];
    const dx = wx - n.x, dy = wy - n.y;
    if (Math.sqrt(dx*dx+dy*dy) <= n.r + 2) return n;
  }}
  return null;
}}

canvas.addEventListener('mousedown', e => {{
  const w = worldPos(e.clientX, e.clientY);
  const hit = hitNode(w.x, w.y);
  if (hit) {{ drag = {{ node: hit, ox: w.x - hit.x, oy: w.y - hit.y }}; hit.pinned = true; }}
  else pan = {{ ox: e.clientX - cam.x, oy: e.clientY - cam.y }};
}});

canvas.addEventListener('mousemove', e => {{
  if (drag) {{
    const w = worldPos(e.clientX, e.clientY);
    drag.node.x = w.x - drag.ox;
    drag.node.y = w.y - drag.oy;
    drag.node.vx = drag.node.vy = 0;
  }} else if (pan) {{
    cam.x = e.clientX - pan.ox;
    cam.y = e.clientY - pan.oy;
  }}
}});

canvas.addEventListener('mouseup', () => {{ drag = pan = null; }});

canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.91;
  cam.zoom = Math.max(0.2, Math.min(4, cam.zoom * factor));
}}, {{ passive: false }});

// --- physics ---
const REPEL = 4000;
const SPRING = 0.04;
const REST = {{
  owns: 100, scope: 140, alias: 80, forbidden: 80, default: 110
}};
const DAMP = 0.82;
const CENTER = 0.005;

function tick() {{
  // repulsion
  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i+1; j < nodes.length; j++) {{
      const a = nodes[i], b = nodes[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      const d2 = dx*dx + dy*dy || 1;
      const f = REPEL / d2;
      const inv = 1 / Math.sqrt(d2);
      dx *= inv; dy *= inv;
      a.vx -= f*dx; a.vy -= f*dy;
      b.vx += f*dx; b.vy += f*dy;
    }}
  }}

  // springs
  for (const e of edges) {{
    const a = nodeById[e.source], b = nodeById[e.target];
    if (!a || !b) continue;
    let dx = b.x - a.x, dy = b.y - a.y;
    const d = Math.sqrt(dx*dx+dy*dy) || 1;
    const rest = REST[e.kind] ?? REST.default;
    const f = (d - rest) * SPRING;
    dx /= d; dy /= d;
    a.vx += f*dx; a.vy += f*dy;
    b.vx -= f*dx; b.vy -= f*dy;
  }}

  // center gravity
  for (const n of nodes) {{
    n.vx += (0 - n.x) * CENTER;
    n.vy += (0 - n.y) * CENTER;
  }}

  // integrate
  for (const n of nodes) {{
    if (n.pinned && drag?.node === n) continue;
    n.vx *= DAMP; n.vy *= DAMP;
    n.x += n.vx; n.y += n.vy;
  }}
}}

// --- render ---
function hexAlpha(hex, a) {{
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

function draw() {{
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(W/2 + cam.x, H/2 + cam.y);
  ctx.scale(cam.zoom, cam.zoom);

  // edges
  for (const e of edges) {{
    const a = nodeById[e.source], b = nodeById[e.target];
    if (!a || !b) continue;

    const dx = b.x - a.x, dy = b.y - a.y;
    const d = Math.sqrt(dx*dx+dy*dy) || 1;
    const ux = dx/d, uy = dy/d;
    const sx = a.x + ux*a.r, sy = a.y + uy*a.r;
    const ex = b.x - ux*b.r, ey = b.y - uy*b.r;

    ctx.beginPath();
    if (e.kind === 'alias') {{
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#374151';
      ctx.lineWidth = 1;
    }} else if (e.kind === 'forbidden') {{
      ctx.setLineDash([]);
      ctx.strokeStyle = hexAlpha('#dc2626', 0.5);
      ctx.lineWidth = 1;
    }} else if (e.kind === 'scope') {{
      ctx.setLineDash([]);
      ctx.strokeStyle = '#252838';
      ctx.lineWidth = 1.5;
    }} else {{
      ctx.setLineDash([]);
      ctx.strokeStyle = '#1e2130';
      ctx.lineWidth = 1.5;
    }}
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.stroke();

    // arrowhead on alias edges
    if (e.kind === 'alias') {{
      ctx.setLineDash([]);
      ctx.fillStyle = '#374151';
      const angle = Math.atan2(ey-sy, ex-sx);
      ctx.save();
      ctx.translate(ex, ey);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-7, -3.5);
      ctx.lineTo(-7, 3.5);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }}
  }}
  ctx.setLineDash([]);

  // nodes
  for (const n of nodes) {{
    // glow for scopes
    if (['global','domain','context'].includes(n.type)) {{
      const g = ctx.createRadialGradient(n.x, n.y, n.r*0.5, n.x, n.y, n.r*2);
      g.addColorStop(0, hexAlpha(n.color, 0.15));
      g.addColorStop(1, hexAlpha(n.color, 0));
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r*2, 0, Math.PI*2);
      ctx.fillStyle = g;
      ctx.fill();
    }}

    // circle
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
    ctx.fillStyle = hexAlpha(n.color, n.type === 'alias' ? 0.25 : 0.18);
    ctx.fill();
    ctx.strokeStyle = n.color;
    ctx.lineWidth = n.type === 'alias' ? 1 : 1.5;
    ctx.stroke();

    // label
    const fs = n.type === 'global' ? 13 :
                n.type === 'domain' || n.type === 'context' ? 11 : 10;
    ctx.font = `${{['global','domain','context'].includes(n.type) ? 600 : 500}} ${{fs}}px system-ui`;
    ctx.fillStyle = n.type === 'alias' ? '#6b7280' : '#e2e4f0';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(n.label, n.x, n.y);
  }}

  ctx.restore();
}}

function loop() {{
  for (let i = 0; i < 3; i++) tick();
  draw();
  requestAnimationFrame(loop);
}}
loop();
</script>
</body>
</html>
"""


def _generate_html(config: Config) -> str:
    graph = _build_graph(config)
    assert "nodes" in graph and "edges" in graph, "graph must have nodes and edges"
    html = _HTML_TEMPLATE.format(data=json.dumps(graph))
    assert html.startswith("<!DOCTYPE html>"), "output must be an HTML document"
    return html


SERIES = ("#3987e5", "#d95926", "#199e70")
OTHER = "#8a8a80"
OUTLIER = "#fab219"


def _scope_colors(points: list[Point]) -> dict[str, str]:
    assert points, "need points to colour"
    assert all(point.scope for point in points), "every point must carry a scope"
    ranked = [scope for scope, _ in Counter(point.scope for point in points).most_common()]
    return {
        scope: SERIES[index] if index < len(SERIES) else OTHER for index, scope in enumerate(ranked)
    }


def _gap(a: Point, b: Point) -> float:
    assert a.name and b.name, "both points must have names"
    assert a is not b, "a point has no gap to itself"
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _spacing(points: list[Point]) -> float:
    assert points, "need points to measure spacing"
    assert all(point.name for point in points), "every point must have a name"
    if len(points) < 2:
        return 1.0
    gaps = sorted(min(_gap(p, o) for o in points if o is not p) for p in points)
    return gaps[len(gaps) // 2] or 1.0


def _spanning_edges(members: list[Point]) -> list[list[list[float]]]:
    assert members, "need members to span"
    assert all(member.name for member in members), "every member must have a name"
    reached, waiting, out = [members[0]], members[1:], []
    while waiting:
        near, joining = min(
            ((a, b) for a in reached for b in waiting), key=lambda pair: _gap(*pair)
        )
        waiting.remove(joining)
        reached.append(joining)
        out.append([[near.x, near.y], [joining.x, joining.y]])
    assert len(out) == len(members) - 1, "a context must span into one connected region"
    return out


def _lumps(member: Point, radius: float) -> list[list[float]]:
    assert member.name, "a lump needs a named point"
    assert radius > 0.0, "radius must be a positive distance"
    seed = zlib.crc32(member.name.encode())
    angle = radians((seed >> 8) % 360)
    return [
        [member.x, member.y, 0.85 + (seed % 41) / 100.0],
        [member.x + cos(angle) * radius * 0.6, member.y + sin(angle) * radius * 0.6, 0.7],
    ]


def _regions(points: list[Point], radius: float) -> list[dict]:
    assert points, "need points to bound"
    assert radius > 0.0, "radius must be a positive distance"
    grouped: dict[str, list[Point]] = defaultdict(list)
    for point in points:
        grouped[point.scope].append(point)
    return [
        {
            "scope": scope,
            "discs": [lump for m in members for lump in _lumps(m, radius)],
            "edges": _spanning_edges(members),
        }
        for scope, members in sorted(grouped.items())
    ]


def _anchors(points: list[Point]) -> set[str]:
    assert points, "need points to pick anchors from"
    assert all(point.name for point in points), "every point must have a name"
    grouped: dict[int, list[Point]] = defaultdict(list)
    for point in points:
        grouped[point.cluster].append(point)
    out: set[str] = set()
    for members in grouped.values():
        if len(members) < 2:
            continue
        out.add(
            min(
                members,
                key=lambda m: sum((m.x - o.x) ** 2 + (m.y - o.y) ** 2 for o in members),
            ).name
        )
    return out


def _build_scatter(points: list[Point], insights: list[Insight]) -> dict:
    assert all(point.name for point in points), "every point must have a name"
    assert all(insight.rule for insight in insights), "every insight must carry a rule"
    if not points:
        return {"points": [], "regions": [], "legend": [], "radius": 0.0}
    colors = _scope_colors(points)
    flagged = {name for i in insights if i.rule == "context-outlier" for name in i.names}
    anchors = _anchors(points)
    spacing = _spacing(points)
    return {
        "points": [
            {
                "name": point.name,
                "x": point.x,
                "y": point.y,
                "role": point.role,
                "scope": point.scope,
                "color": colors[point.scope],
                "outlier": point.name in flagged,
                "anchor": point.name in anchors,
            }
            for point in points
        ],
        "regions": _regions(points, spacing * 0.75),
        "radius": spacing * 0.75,
        "legend": [{"scope": scope, "color": color} for scope, color in colors.items()],
    }


_SCATTER_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DDD Vocabulary Map</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d0f17; overflow: hidden; font-family: system-ui, sans-serif; }
  canvas { display: block; }
  #hint { position: fixed; top: 1.5rem; right: 1.5rem; font-size: 0.72rem; color: #374151; }
  #legend { position: fixed; bottom: 1.5rem; left: 1.5rem; display: flex; gap: 1rem; flex-wrap: wrap; }
  .leg { display: flex; align-items: center; gap: 0.35rem; font-size: 0.72rem; color: #6b7280; }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .tri { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
         border-bottom: 9px solid #8a8a80; }
  #title { position: fixed; top: 1.5rem; left: 1.5rem; font-size: 1.1rem; font-weight: 700;
           color: #e2e4f0; letter-spacing: -0.03em; }
  #caption { position: fixed; top: 3rem; left: 1.5rem; font-size: 0.72rem; color: #6b7280;
             max-width: 26rem; line-height: 1.5; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="title">DDD Vocabulary Map</div>
<div id="hint">scroll to zoom · drag to pan · hover a context for its names</div>
<div id="legend"></div>
<div id="caption">Names placed by embedding similarity, flattened with PCA. Distance is
approximate: one named boundary per bounded context, stretched to hold every name that
belongs to it.</div>
<script>
const DATA = __DATA__;
const OUTLIER = '__OUTLIER__';
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const shade = document.createElement('canvas').getContext('2d');
let W, H;

function resize() {
  W = canvas.width = shade.canvas.width = window.innerWidth;
  H = canvas.height = shade.canvas.height = window.innerHeight;
}
resize();
window.addEventListener('resize', () => { resize(); draw(); });

const xs = DATA.points.map(p => p.x), ys = DATA.points.map(p => p.y);
const span = {
  x0: Math.min(...xs), x1: Math.max(...xs),
  y0: Math.min(...ys), y1: Math.max(...ys),
};
let cam = { x: 0, y: 0, zoom: 1 };

function fit(p) {
  const pad = 90;
  const wide = (span.x1 - span.x0) || 1, tall = (span.y1 - span.y0) || 1;
  const s = Math.min((W - pad * 2) / wide, (H - pad * 2) / tall);
  return {
    x: (W - wide * s) / 2 + (p[0] - span.x0) * s,
    y: (H - tall * s) / 2 + (p[1] - span.y0) * s,
  };
}

function screen(p) {
  const f = fit(p);
  return { x: (f.x - W / 2) * cam.zoom + W / 2 + cam.x, y: (f.y - H / 2) * cam.zoom + H / 2 + cam.y };
}

let taken = [];
let hot = null;

function labelFits(at, width) {
  const box = { x0: at.x - width / 2, x1: at.x + width / 2, y0: at.y - 9, y1: at.y };
  const clash = taken.some(t => box.x0 < t.x1 && box.x1 > t.x0 && box.y0 < t.y1 && box.y1 > t.y0);
  if (!clash) taken[taken.length] = box;
  return !clash;
}

function marker(p, at) {
  ctx.beginPath();
  if (p.role === 'verb') {
    ctx.moveTo(at.x, at.y - 6);
    ctx.lineTo(at.x + 5.5, at.y + 4);
    ctx.lineTo(at.x - 5.5, at.y + 4);
    ctx.closePath();
  } else {
    ctx.arc(at.x, at.y, 5.5, 0, Math.PI * 2);
  }
  ctx.fillStyle = alpha(p.color, 0.85);
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = p.outlier ? OUTLIER : '#0d0f17';
  const lit = hot !== null && p.scope === hot.scope;
  if (p.outlier || p.anchor || lit || cam.zoom > 1.4) {
    ctx.font = '500 10px system-ui';
    ctx.textAlign = 'center';
    const spot = { x: at.x, y: at.y - 11 };
    if (p.outlier || labelFits(spot, ctx.measureText(p.name).width)) {
      ctx.fillStyle = p.outlier ? OUTLIER : (lit ? '#e8e9f2' : '#c3c2b7');
      ctx.fillText(p.name, spot.x, spot.y);
    }
  }
  ctx.stroke();
}

function alpha(hex, a) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${a})`;
}

function blobRadius() {
  const from = screen([0, 0]), to = screen([DATA.radius, 0]);
  return Math.max(9, Math.hypot(to.x - from.x, to.y - from.y));
}

function blob(region, r) {
  shade.beginPath();
  for (const disc of region.discs) {
    const at = screen(disc), lump = Math.max(2, r * disc[2]);
    shade.moveTo(at.x + lump, at.y);
    shade.arc(at.x, at.y, lump, 0, Math.PI * 2);
  }
  shade.fill();
  shade.lineWidth = r * 2;
  shade.lineCap = shade.lineJoin = 'round';
  shade.beginPath();
  for (const [a, b] of region.edges) {
    const from = screen(a), to = screen(b);
    shade.moveTo(from.x, from.y);
    shade.lineTo(to.x, to.y);
  }
  if (region.edges.length) shade.stroke();
}

function bounds(region, r) {
  const at = region.discs.map(screen), pad = r * 1.3 + 6;
  const x0 = Math.min(...at.map(p => p.x)) - pad, y0 = Math.min(...at.map(p => p.y)) - pad;
  return { x: x0, y: y0, w: Math.max(...at.map(p => p.x)) + pad - x0,
           h: Math.max(...at.map(p => p.y)) + pad - y0, top: Math.min(...at.map(p => p.y)) };
}

function paste(box, a) {
  ctx.globalAlpha = a;
  ctx.drawImage(shade.canvas, box.x, box.y, box.w, box.h, box.x, box.y, box.w, box.h);
  ctx.globalAlpha = 1;
}

function inside(region, at, r) {
  for (const disc of region.discs) {
    const p = screen(disc);
    if (Math.hypot(p.x - at.x, p.y - at.y) <= Math.max(2, r * disc[2])) return true;
  }
  for (const [a, b] of region.edges) {
    const from = screen(a), to = screen(b);
    const dx = to.x - from.x, dy = to.y - from.y, span = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((at.x - from.x) * dx + (at.y - from.y) * dy) / span));
    if (Math.hypot(from.x + dx * t - at.x, from.y + dy * t - at.y) <= r) return true;
  }
  return false;
}

function regionAt(at) {
  const r = blobRadius();
  return DATA.regions.find(region => inside(region, at, r)) ?? null;
}

function bound(region) {
  const r = blobRadius(), box = bounds(region, r), lit = region === hot;
  shade.clearRect(box.x, box.y, box.w, box.h);
  shade.globalCompositeOperation = 'source-over';
  shade.fillStyle = shade.strokeStyle = region.color;
  blob(region, r);
  paste(box, lit ? 0.24 : 0.13);
  shade.globalCompositeOperation = 'destination-out';
  blob(region, r - 2.5);
  paste(box, lit ? 0.9 : 0.55);
  ctx.font = lit ? '700 13px system-ui' : '600 11px system-ui';
  ctx.fillStyle = alpha(region.color, lit ? 1 : 0.8);
  ctx.textAlign = 'center';
  ctx.fillText(region.scope, box.x + box.w / 2, box.top - r - 6);
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  taken = [];
  for (const region of DATA.regions) if (region !== hot) bound(region);
  if (hot) bound(hot);
  for (const p of DATA.points) marker(p, screen([p.x, p.y]));
}

document.getElementById('legend').innerHTML = DATA.legend
  .map(l => `<div class="leg"><div class="dot" style="background:${l.color}"></div>${l.scope}</div>`)
  .join('') +
  `<div class="leg"><div class="dot" style="background:#8a8a80"></div>noun</div>
   <div class="leg"><div class="tri"></div>verb</div>
   <div class="leg"><div class="dot" style="background:transparent;border:2px solid ${OUTLIER}"></div>outlier</div>`;

let pan = null;
canvas.addEventListener('mousedown', e => { pan = { ox: e.clientX - cam.x, oy: e.clientY - cam.y }; });
canvas.addEventListener('mouseup', () => { pan = null; });
canvas.addEventListener('mousemove', e => {
  if (pan) {
    cam.x = e.clientX - pan.ox;
    cam.y = e.clientY - pan.oy;
    draw();
    return;
  }
  const found = regionAt({ x: e.clientX, y: e.clientY });
  if (found === hot) return;
  hot = found;
  canvas.style.cursor = hot ? 'pointer' : 'default';
  draw();
});
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  cam.zoom = Math.max(0.3, Math.min(6, cam.zoom * (e.deltaY < 0 ? 1.1 : 0.91)));
  draw();
}, { passive: false });

draw();
</script>
</body>
</html>
"""


def _generate_scatter(points: list[Point], insights: list[Insight]) -> str:
    scatter = _build_scatter(points, insights)
    assert "points" in scatter and "regions" in scatter, "scatter must have points and regions"
    colors = {entry["scope"]: entry["color"] for entry in scatter["legend"]}
    for shape in scatter["regions"]:
        shape["color"] = colors[shape["scope"]]
    html = _SCATTER_TEMPLATE.replace("__DATA__", json.dumps(scatter)).replace(
        "__OUTLIER__", OUTLIER
    )
    assert html.startswith("<!DOCTYPE html>"), "output must be an HTML document"
    return html
