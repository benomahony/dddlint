import json

from .config import Config

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
