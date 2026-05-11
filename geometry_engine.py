"""
geometry_engine.py
─────────────────────────────────────────────────────────────
JSON 几何描述 → GeoGebra 命令翻译器

设计原则：
1. AI 只输出受限的结构化 JSON，永远不写绘图代码
2. 此模块把 JSON 翻译成 GeoGebra 的 evalCommand 字符串
3. 每个图元有唯一 id，便于步骤化显隐控制
4. 出错时 fail-soft：跳过坏元素，不让整张图崩
"""

from __future__ import annotations
import json
import html
from typing import Any


# ─── 支持的几何题类型 ────────────────────────────────────────────────────────
GEOMETRY_TYPES = {
    "triangle":  "三角形",
    "circle":    "圆",
    "coord":     "坐标几何",
    "similar":   "相似/全等",
    "area":      "面积问题",
    "symmetry":  "对称/旋转",
    "polygon":   "多边形",
    "generic":   "其他几何",
}


# ─── 支持的图元类型（白名单）────────────────────────────────────────────────
# 任何不在此列表的 kind 会被忽略 —— 防御性编码
PRIMITIVE_KINDS = {
    "point",
    "segment",
    "ray",
    "line",
    "polygon",
    "circle_through",   # 圆心 O + 经过点 A
    "circle_radius",    # 圆心 O + 半径 r
    "tangent",          # 切线
    "perpendicular",    # 过某点作某线的垂线
    "parallel",         # 过某点作某线的平行线
    "altitude",         # 三角形高
    "median",           # 中线
    "angle_bisector",   # 角平分线
    "midpoint",         # 中点
    "right_angle",      # 直角标记（小方块）
    "angle_arc",        # 角度弧标记（带数值）
    "label",            # 文本标注
}


# ─── 默认调色板（暗色主题友好）──────────────────────────────────────────────
PALETTE = {
    "primary":   "#60A5FA",  # 蓝 — 默认线段
    "secondary": "#F472B6",  # 粉 — 辅助线
    "accent":    "#F5C842",  # 金 — 高亮
    "success":   "#4ADE80",  # 绿 — 已知量
    "danger":    "#F87171",  # 红 — 关键标注
    "fill":      "#F5C842",  # 金 — 多边形填充
}


# ─── JSON 校验 & 修复 ─────────────────────────────────────────────────────
def _primitive_references(prim: dict) -> list[str]:
    """Return all point/line names this primitive references.
    Used to drop primitives that reference undefined names → prevents
    GeoGebra's "argument doesn't match rule: vector vA" error."""
    refs = []
    kind = prim.get("kind")
    # Direct point references
    for k in ("from", "to", "at", "vertex", "a", "c", "from_a", "from_c",
              "center", "through", "name"):
        v = prim.get(k)
        if isinstance(v, str):
            refs.append(v)
    # Array references
    for k in ("vertices", "to_side"):
        v = prim.get(k)
        if isinstance(v, list):
            refs.extend([x for x in v if isinstance(x, str)])
    # "circle" and "to_line" reference other primitive IDs, handled separately
    return refs


def validate_geometry_spec(spec: dict) -> dict:
    """检查并修复 AI 输出的 JSON。返回保证字段齐全的新字典。

    关键防御：
    1. 收集所有已定义的点名
    2. 收集所有 primitive 的 id
    3. 任何引用未定义点名的 primitive 会被跳过
    这避免了 GeoGebra 报"参数不符合规则: 向量 vA"等错误。
    """
    if not isinstance(spec, dict):
        return _empty_spec()

    out = {
        "geometry_type": spec.get("geometry_type", "generic"),
        "title": str(spec.get("title", "几何示意图"))[:80],
        "points": [],
        "primitives": [],
        "auxiliary_steps": [],
    }

    if out["geometry_type"] not in GEOMETRY_TYPES:
        out["geometry_type"] = "generic"

    # ── Pass 1: collect valid point names ──
    seen_names = set()
    for p in spec.get("points", []):
        if not isinstance(p, dict): continue
        name = str(p.get("name", "")).strip()
        if not name or name in seen_names: continue
        if not name[0].isalpha(): continue
        try:
            x = float(p.get("x", 0))
            y = float(p.get("y", 0))
        except (TypeError, ValueError):
            continue
        seen_names.add(name)
        out["points"].append({"name": name, "x": x, "y": y})

    # ── Pass 2: scan primitives and track which IDs will exist ──
    # First pass: build a list of valid primitive IDs
    pid_counter = 0
    candidate_prims = []
    for prim in spec.get("primitives", []):
        if not isinstance(prim, dict): continue
        kind = prim.get("kind")
        if kind not in PRIMITIVE_KINDS: continue
        pid = prim.get("id") or f"p{pid_counter}"
        pid_counter += 1
        new_prim = dict(prim)
        new_prim["id"] = _safe_id(pid)
        # "circle" / "to_line" references resolve to another primitive's id
        # so they need to also be in scope
        candidate_prims.append(new_prim)

    valid_prim_ids = {p["id"] for p in candidate_prims}
    valid_names = seen_names | valid_prim_ids  # both points and prim ids

    # Some primitives create new point names too (midpoint with `name` field)
    for p in candidate_prims:
        if p.get("kind") == "midpoint" and isinstance(p.get("name"), str):
            valid_names.add(p["name"])

    # ── Pass 3: keep only primitives whose references all exist ──
    dropped = []
    for prim in candidate_prims:
        refs = _primitive_references(prim)
        # Special: "to_line" / "circle" reference primitive IDs
        for k in ("to_line", "circle"):
            v = prim.get(k)
            if isinstance(v, str):
                refs.append(v)

        # Filter: which refs are not in scope?
        unknown = [r for r in refs if r not in valid_names]
        if unknown:
            dropped.append((prim.get("id"), prim.get("kind"), unknown))
            continue
        out["primitives"].append(prim)

    if dropped:
        # Quiet diagnostic — won't fail the render
        import sys
        print(f"[geometry_engine] dropped {len(dropped)} prims w/ unknown refs: "
              f"{dropped[:3]}", file=sys.stderr)

    # ── Pass 4: auxiliary steps (only reference valid prim ids) ──
    kept_ids = {p["id"] for p in out["primitives"]}
    for s in spec.get("auxiliary_steps", []):
        if not isinstance(s, dict): continue
        show = [_safe_id(x) for x in s.get("show", []) if isinstance(x, str)]
        highlight = [_safe_id(x) for x in s.get("highlight", []) if isinstance(x, str)]
        # Drop step entries that reference vanished primitives
        show = [x for x in show if x in kept_ids]
        highlight = [x for x in highlight if x in kept_ids]
        step = {
            "step": int(s.get("step", len(out["auxiliary_steps"]) + 1)),
            "show": show,
            "highlight": highlight,
            "narration": str(s.get("narration", ""))[:200],
        }
        out["auxiliary_steps"].append(step)

    out["auxiliary_steps"].sort(key=lambda x: x["step"])

    # Fallback: ensure at least one step exists with all valid prims visible
    if not out["auxiliary_steps"] and out["primitives"]:
        out["auxiliary_steps"] = [{
            "step": 1,
            "show": [p["id"] for p in out["primitives"]],
            "highlight": [],
            "narration": "完整图形",
        }]

    return out


def _empty_spec():
    return {
        "geometry_type": "generic", "title": "", "points": [],
        "primitives": [], "auxiliary_steps": [],
    }


def _safe_id(s: str) -> str:
    """Sanitize id → only alnum and underscore, avoid GGB conflicts."""
    s = "".join(c if c.isalnum() or c == "_" else "_" for c in str(s))
    if not s or not s[0].isalpha():
        s = "el_" + s
    return s


# ─── JSON → GeoGebra commands ──────────────────────────────────────────────
def spec_to_ggb_commands(spec: dict) -> list[dict]:
    """
    Translate validated spec → list of {id, cmd, color, narration_step}.
    Each entry is a single GeoGebra evalCommand line.
    The frontend uses `id` to toggle visibility per step.
    """
    spec = validate_geometry_spec(spec)
    cmds: list[dict] = []

    # 1. Define all named points first (always visible)
    for p in spec["points"]:
        cmds.append({
            "id":  f"pt_{p['name']}",
            "cmd": f"{p['name']} = ({p['x']}, {p['y']})",
            "type": "point",
            "always_visible": True,
        })

    # 2. Primitives
    for prim in spec["primitives"]:
        translated = _translate_primitive(prim)
        cmds.extend(translated)

    return cmds


def _translate_primitive(prim: dict) -> list[dict]:
    """Convert a single primitive dict to one or more GGB command entries."""
    kind = prim["kind"]
    pid  = prim["id"]
    color = prim.get("color") or _default_color_for(kind)

    def entry(suffix: str, cmd: str, ggb_label: str = None):
        return {
            "id": f"{pid}{suffix}",
            "ggb_label": ggb_label or f"{pid}{suffix}",
            "cmd": cmd,
            "type": kind,
            "color": color,
            "label_text": prim.get("label", ""),
        }

    # ── point ──
    if kind == "point":
        name = prim.get("name", pid)
        x, y = prim.get("x", 0), prim.get("y", 0)
        return [entry("", f"{name} = ({x}, {y})", ggb_label=name)]

    # ── segment ──
    if kind == "segment":
        a, b = prim.get("from"), prim.get("to")
        if not (a and b): return []
        return [entry("", f"{pid} = Segment({a}, {b})")]

    # ── ray ──
    if kind == "ray":
        a, b = prim.get("from"), prim.get("to")
        if not (a and b): return []
        return [entry("", f"{pid} = Ray({a}, {b})")]

    # ── line ──
    if kind == "line":
        a, b = prim.get("from"), prim.get("to")
        if not (a and b): return []
        return [entry("", f"{pid} = Line({a}, {b})")]

    # ── polygon ──
    if kind == "polygon":
        verts = prim.get("vertices", [])
        if len(verts) < 3: return []
        return [entry("", f"{pid} = Polygon({', '.join(verts)})")]

    # ── circle through ──
    if kind == "circle_through":
        center = prim.get("center")
        through = prim.get("through")
        if not (center and through): return []
        return [entry("", f"{pid} = Circle({center}, {through})")]

    # ── circle radius ──
    if kind == "circle_radius":
        center = prim.get("center")
        radius = prim.get("radius", 1)
        if not center: return []
        return [entry("", f"{pid} = Circle({center}, {radius})")]

    # ── tangent ──
    if kind == "tangent":
        # Tangent[<Point>, <Conic>]
        point = prim.get("from")
        circle_id = prim.get("circle")
        if not (point and circle_id): return []
        return [entry("", f"{pid} = Tangent({point}, {circle_id})")]

    # ── perpendicular ──
    if kind == "perpendicular":
        point = prim.get("from")
        line_id = prim.get("to_line")
        if not (point and line_id): return []
        return [entry("", f"{pid} = PerpendicularLine({point}, {line_id})")]

    # ── parallel ──
    if kind == "parallel":
        point = prim.get("from")
        line_id = prim.get("to_line")
        if not (point and line_id): return []
        return [entry("", f"{pid} = Line({point}, {line_id})")]

    # ── altitude (三角形某顶点的高) ──
    if kind == "altitude":
        vertex = prim.get("from")
        side = prim.get("to_side")  # tuple of two point names
        if not (vertex and side and len(side) == 2): return []
        a, b = side
        # 创建底边的 line（用唯一 id 避免冲突）
        base_id = f"{pid}_base"
        line_cmd = f"{base_id} = Line({a}, {b})"
        alt_cmd  = f"{pid} = PerpendicularLine({vertex}, {base_id})"
        return [
            {"id": f"{pid}_base_helper", "cmd": line_cmd, "type": "altitude_base",
             "color": "#444", "ggb_label": base_id, "hidden_helper": True},
            entry("", alt_cmd),
        ]

    # ── median (三角形中线) ──
    if kind == "median":
        vertex = prim.get("from")
        side = prim.get("to_side")
        if not (vertex and side and len(side) == 2): return []
        a, b = side
        mid_id = f"{pid}_mid"
        return [
            {"id": f"{pid}_mid_helper", "cmd": f"{mid_id} = Midpoint({a}, {b})",
             "type": "median_helper", "color": "#444", "ggb_label": mid_id, "hidden_helper": True},
            entry("", f"{pid} = Segment({vertex}, {mid_id})"),
        ]

    # ── angle bisector ──
    if kind == "angle_bisector":
        a, b, c = prim.get("a"), prim.get("vertex"), prim.get("c")
        if not (a and b and c): return []
        return [entry("", f"{pid} = AngleBisector({a}, {b}, {c})")]

    # ── midpoint ──
    if kind == "midpoint":
        a, b = prim.get("from"), prim.get("to")
        if not (a and b): return []
        name = prim.get("name", pid)
        return [entry("", f"{name} = Midpoint({a}, {b})", ggb_label=name)]

    # ── right_angle marker ──
    if kind == "right_angle":
        # Angle marker between two segments at a vertex
        a, vertex, c = prim.get("from_a"), prim.get("at"), prim.get("from_c")
        if not (a and vertex and c): return []
        return [entry("", f"{pid} = Angle({a}, {vertex}, {c})")]

    # ── angle_arc ──
    if kind == "angle_arc":
        a, vertex, c = prim.get("a"), prim.get("vertex"), prim.get("c")
        if not (a and vertex and c): return []
        return [entry("", f"{pid} = Angle({a}, {vertex}, {c})")]

    # ── label ──
    if kind == "label":
        x = prim.get("x", 0); y = prim.get("y", 0)
        text = str(prim.get("text", "")).replace('"', '\\"')
        return [entry("", f'{pid} = Text("{text}", ({x}, {y}))')]

    return []


def _default_color_for(kind: str) -> str:
    if kind in ("polygon",):                                     return PALETTE["fill"]
    if kind in ("altitude", "median", "angle_bisector",
                "perpendicular", "parallel", "midpoint",
                "tangent"):                                       return PALETTE["secondary"]
    if kind in ("right_angle", "angle_arc"):                     return PALETTE["accent"]
    if kind == "label":                                          return PALETTE["accent"]
    return PALETTE["primary"]


# ─── HTML/JS GeoGebra applet generator ─────────────────────────────────────
def build_geogebra_html(spec: dict, height: int = 480) -> str:
    """Return a self-contained HTML string with embedded GeoGebra applet
    that renders the spec and supports step-by-step visibility toggling."""
    spec = validate_geometry_spec(spec)
    commands = spec_to_ggb_commands(spec)
    steps = spec["auxiliary_steps"]

    # Auto-fit bounds based on points
    xs = [p["x"] for p in spec["points"]] or [0, 5]
    ys = [p["y"] for p in spec["points"]] or [0, 5]
    pad_x = max(2, (max(xs) - min(xs)) * 0.3)
    pad_y = max(2, (max(ys) - min(ys)) * 0.3)
    xmin, xmax = min(xs) - pad_x, max(xs) + pad_x
    ymin, ymax = min(ys) - pad_y, max(ys) + pad_y

    # Serialize to JSON for embedding
    cmds_json = json.dumps(commands, ensure_ascii=False)
    steps_json = json.dumps(steps, ensure_ascii=False)
    title_safe = html.escape(spec["title"])
    type_label = GEOMETRY_TYPES.get(spec["geometry_type"], "几何")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0; padding: 0;
    background: #0C1829;
    font-family: 'PingFang SC', 'Noto Sans SC', sans-serif;
    color: #EEF2FF;
  }}
  .geo-wrap {{ padding: 0; }}
  .geo-header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: .6rem 1rem; background: rgba(245,200,66,.06);
    border-bottom: 1px solid rgba(245,200,66,.2);
  }}
  .geo-title {{ color: #F5C842; font-size: .9rem; font-weight: 600; }}
  .geo-tag   {{ color: #60A5FA; font-size: .75rem; }}
  #ggb-applet {{ background: #FFFFFF; }}
  .step-panel {{
    background: rgba(99,102,241,.08); border-top: 1px solid rgba(99,102,241,.25);
    padding: .8rem 1rem;
  }}
  .step-controls {{ display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }}
  .step-btn {{
    background: linear-gradient(135deg,#F5C842,#F59E0B); border: none;
    color: #0C1829; font-weight: 700; padding: .35rem .9rem;
    border-radius: 6px; cursor: pointer; font-size: .85rem;
  }}
  .step-btn:disabled {{ opacity: .35; cursor: not-allowed; }}
  .step-counter {{ color: #94A3B8; font-size: .8rem; }}
  .step-narration {{
    background: rgba(96,165,250,.1); border-left: 3px solid #60A5FA;
    padding: .6rem .9rem; margin-top: .6rem;
    border-radius: 6px; font-size: .9rem; line-height: 1.7;
    color: #E0E7FF;
  }}
</style>
</head>
<body>
<div class="geo-wrap">
  <div class="geo-header">
    <span class="geo-title">📐 {title_safe}</span>
    <span class="geo-tag">类型：{type_label}</span>
  </div>
  <div id="ggb-applet"></div>
  <div class="step-panel">
    <div class="step-controls">
      <button class="step-btn" id="prev-btn" onclick="goPrev()">← 上一步</button>
      <button class="step-btn" id="next-btn" onclick="goNext()">下一步 →</button>
      <span class="step-counter" id="step-counter"></span>
      <button class="step-btn" style="margin-left:auto;background:rgba(255,255,255,.1);color:#fff;" onclick="resetView()">🔄 重置视角</button>
    </div>
    <div class="step-narration" id="narration">准备中...</div>
  </div>
</div>

<script src="https://www.geogebra.org/apps/deployggb.js"></script>
<script>
  const COMMANDS = {cmds_json};
  const STEPS    = {steps_json};
  let currentStep = 0;
  let ggbApp = null;

  const params = {{
    appName: "geometry",
    width:  Math.max(window.innerWidth - 0, 360),
    height: {height},
    showToolBar: false,
    showAlgebraInput: false,
    showMenuBar: false,
    showResetIcon: false,
    enableLabelDrags: false,
    enableShiftDragZoom: true,
    enableRightClick: false,
    showZoomButtons: true,
    capturingThreshold: null,
    showFullscreenButton: false,
    scale: 1,
    perspective: "G",  // graphics view only
    appletOnLoad: function(api) {{
      ggbApp = api;
      try {{
        api.setCoordSystem({xmin}, {xmax}, {ymin}, {ymax});
      }} catch(e){{ console.warn(e); }}

      // SUPPRESS GeoGebra's native error popup — we handle errors silently
      try {{ api.setErrorDialogsActive(false); }} catch(e){{}}

      // Execute every command, then hide everything by default
      const failedCmds = [];
      for (const c of COMMANDS) {{
        try {{
          const ok = api.evalCommand(c.cmd);
          if (ok === false) {{
            // Command rejected by GGB (bad syntax / unknown reference)
            failedCmds.push(c.id);
            continue;
          }}
          const lbl = c.ggb_label || c.id;
          if (c.color) {{
            try {{
              const rgb = hexToRgb(c.color);
              api.setColor(lbl, rgb.r, rgb.g, rgb.b);
            }} catch(e){{}}
          }}
          // Hide helper construction lines completely
          if (c.hidden_helper) {{
            api.setVisible(lbl, false);
            api.setLabelVisible(lbl, false);
          }} else if (!c.always_visible) {{
            api.setVisible(lbl, false);
          }}
        }} catch(e) {{
          console.warn("GGB command failed:", c.cmd, e);
        }}
      }}

      applyStep(0);
    }}
  }};

  function hexToRgb(hex) {{
    hex = hex.replace("#", "");
    if (hex.length === 3) hex = hex.split("").map(c => c+c).join("");
    return {{
      r: parseInt(hex.slice(0,2),16),
      g: parseInt(hex.slice(2,4),16),
      b: parseInt(hex.slice(4,6),16),
    }};
  }}

  function applyStep(idx) {{
    if (!ggbApp) return;
    if (idx < 0 || idx >= STEPS.length) return;
    currentStep = idx;

    // Compute cumulative visibility: a primitive shows if it appears in
    // any step <= idx. Steps are *additive*: each new step keeps prior elements.
    const visible = new Set();
    const highlighted = new Set();
    for (let i = 0; i <= idx; i++) {{
      (STEPS[i].show || []).forEach(s => visible.add(s));
    }}
    (STEPS[idx].highlight || []).forEach(h => highlighted.add(h));

    // Apply visibility to each command (skip hidden helpers — they stay hidden)
    for (const c of COMMANDS) {{
      const lbl = c.ggb_label || c.id;
      if (c.hidden_helper) continue;
      try {{
        if (c.always_visible) {{
          ggbApp.setVisible(lbl, true);
        }} else {{
          // Match by base id (some primitives expand to id + suffix)
          const base = c.id;
          let show = false;
          for (const v of visible) {{
            if (base === v || base.startsWith(v) || v.startsWith(base)) {{
              show = true; break;
            }}
          }}
          ggbApp.setVisible(lbl, show);
        }}
      }} catch(e){{}}

      // Highlight: thicken line, change color tint
      try {{
        const base = c.id;
        let isHi = false;
        for (const h of highlighted) {{
          if (base === h || base.startsWith(h) || h.startsWith(base)) {{
            isHi = true; break;
          }}
        }}
        ggbApp.setLineThickness(lbl, isHi ? 7 : 3);
      }} catch(e){{}}
    }}

    // Update UI
    const total = STEPS.length;
    document.getElementById("step-counter").textContent = `第 ${{idx + 1}} / ${{total}} 步`;
    document.getElementById("prev-btn").disabled = (idx === 0);
    document.getElementById("next-btn").disabled = (idx === total - 1);
    document.getElementById("narration").textContent =
      STEPS[idx].narration || "（无说明）";
  }}

  function goNext() {{ if (currentStep < STEPS.length - 1) applyStep(currentStep + 1); }}
  function goPrev() {{ if (currentStep > 0) applyStep(currentStep - 1); }}
  function resetView() {{
    if (ggbApp) {{
      try {{ ggbApp.setCoordSystem({xmin}, {xmax}, {ymin}, {ymax}); }} catch(e){{}}
    }}
  }}

  document.addEventListener("DOMContentLoaded", function() {{
    const applet = new GGBApplet(params, true);
    applet.inject("ggb-applet");
  }});
</script>
</body>
</html>
"""


# ─── 测试用 mock 数据 ──────────────────────────────────────────────────────
def example_triangle_with_altitude() -> dict:
    """Demo: 三角形 ABC，作 BC 边的高 AH"""
    return {
        "geometry_type": "triangle",
        "title": "三角形高的作法",
        "points": [
            {"name": "A", "x": 1, "y": 4},
            {"name": "B", "x": 0, "y": 0},
            {"name": "C", "x": 5, "y": 0},
        ],
        "primitives": [
            {"id": "tri",   "kind": "polygon", "vertices": ["A", "B", "C"]},
            {"id": "alt_a", "kind": "altitude", "from": "A", "to_side": ["B", "C"]},
        ],
        "auxiliary_steps": [
            {"step": 1, "show": ["tri"],            "narration": "先看三角形 ABC"},
            {"step": 2, "show": ["tri", "alt_a"],   "narration": "从顶点 A 作底边 BC 的高",
             "highlight": ["alt_a"]},
        ],
    }
