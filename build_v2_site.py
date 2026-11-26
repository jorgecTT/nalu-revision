#!/usr/bin/env python3
"""Build /web_revision/v2/ WebP assets and index.html across all completed NALU v2 campaigns."""
import json
import re
import subprocess
from pathlib import Path
from PIL import Image

NALU_ROOT = Path("/Users/jcardona/Documents/alex opencode/nalu")
WEB_V2 = NALU_ROOT / "web_revision" / "v2"
V1_HTML = NALU_ROOT / "web_revision" / "index.html"

CAMPAIGN_SPECS = [
    ("correcciones_ana_lote1", "lote1", "✨ Lote 1 Corregidas", "correcciones_ana_lote1", "Lote 1"),
    ("catalogo_macros_7colores_v2", "macros", "🔍 Macros Selector 7×4", "macros_v2", "Macro Selector 7×4"),
    ("catalogo_editorial_v2_ola8", "ola8", "🌊 Ola 8 Editorial", "ola8_editorial", "Ola 8 Editorial"),
    ("catalogo_ola9_costa_y_agua", "ola9", "🏖️ Ola 9 Costa & Agua", "ola9_costa", "Ola 9 · Costa & Agua"),
    ("catalogo_ola10_villas_y_resorts", "ola10", "🏛️ Ola 10 Villas & Resorts", "ola10_villas", "Ola 10 · Villas & Resorts"),
    ("catalogo_ola11_estudio_lujo_y_luz", "ola11", "☀️ Ola 11 Estudio & Luz", "ola11_estudio", "Ola 11 · Estudio & Luz"),
    ("catalogo_ola12_macros_y_candid_sexy", "ola12", "🔥 Ola 12 Macros & Candids", "ola12_sexy", "Ola 12 · Macros & Candids"),
]

COLOR_MAP = {
    "aguamarina": ("Aguamarina", 1),
    "blanco": ("Blanco", 2),
    "arcilla": ("Arcilla", 3),
    "carbon": ("Carbón", 4),
    "arena": ("Arena", 5),
    "laguna": ("Laguna", 6),
    "chocolate": ("Chocolate", 7),
    "duo": ("Dúo / Multi", 8),
    "grupo": ("Dúo / Multi", 8),
}


def sync_webp(src_dir: Path, dst_dir: Path) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for png in sorted(src_dir.glob("*.png")):
        webp = dst_dir / f"{png.stem}.webp"
        if not webp.exists() or png.stat().st_mtime > webp.stat().st_mtime:
            im = Image.open(png).convert("RGB")
            if max(im.size) > 1400:
                im.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            im.save(webp, "WEBP", quality=86, method=5)
        count += 1
    return count


def detect_color(sid: str, name: str):
    low = f"{sid}_{name}".lower()
    if "duo" in low or "_y_" in low or "dúo" in low:
        return "duo", "Dúo / Multi", 8
    for slug, (lbl, rnk) in COLOR_MAP.items():
        if slug in ("duo", "grupo"):
            continue
        if re.search(rf"(?:^|_){slug}(?:$|_)", sid.lower()) or slug in low:
            return slug, lbl, rnk
    return "grupo", "Dúo / Multi", 8


def detect_view(sid: str, name: str):
    low = f"{sid} {name}".lower()
    if "espalda" in low:
        return "espalda", "Espalda"
    return "frente", "Frente"


def lote1_group_label(sid: str) -> str:
    n = int(sid.split("_")[0])
    if n <= 5:
        return "Piloto Aprobado (5)"
    if n <= 15:
        return "Correcciones Ana (10)"
    return "Serie 160 · 7 Colores (6)"


def main():
    v1_html = V1_HTML.read_text(encoding="utf-8")
    m_old = re.search(r"const ALL_ITEMS = (\[.*?\]);", v1_html)
    assert m_old, "ALL_ITEMS not found in web_revision/index.html"
    old_items = json.loads(m_old.group(1))
    for it in old_items:
        if not it["src"].startswith("../"):
            it["src"] = "../" + it["src"]

    all_new = []
    active_tabs = []
    order_counter = 1

    for camp_slug, sec, tab_title, img_subdir, default_grp in CAMPAIGN_SPECS:
        camp_json = NALU_ROOT / "campanas" / camp_slug / "scenes.json"
        out_dir = NALU_ROOT / "output" / camp_slug
        if not camp_json.exists() or not out_dir.exists():
            continue
        pngs = {p.stem: p for p in out_dir.glob("*.png")}
        if not pngs:
            continue

        sync_webp(out_dir, WEB_V2 / "img" / img_subdir)
        data = json.loads(camp_json.read_text(encoding="utf-8"))
        sec_count = 0
        for s in data.get("scenes", []):
            sid = s["id"]
            if sid not in pngs:
                continue
            cslug, clbl, crank = detect_color(sid, s.get("name", ""))
            vw, vw_lbl = detect_view(sid, s.get("name", ""))
            grp_lbl = default_grp
            if camp_slug == "correcciones_ana_lote1":
                grp_lbl = lote1_group_label(sid)
            elif camp_slug == "catalogo_editorial_v2_ola8":
                ser_map = {"A": "Ducha & Caliza", "B": "Golden Hour & Velero", "C": "Estudio Ventanal", "D": "Resort Palmeras"}
                ser_code = s["name"].split("-")[1][0] if "-" in s.get("name", "") else "A"
                grp_lbl = f"Ola 8 · {ser_map.get(ser_code, 'Editorial')}"

            all_new.append({
                "src": f"img/{img_subdir}/{sid}.webp",
                "origSrc": f"{camp_slug}/{sid}.png",
                "file": f"{sid}.png",
                "id": sid,
                "name": s.get("name", sid),
                "color": cslug,
                "colorLabel": clbl,
                "colorRank": crank,
                "view": vw,
                "viewLabel": vw_lbl,
                "isNew": True,
                "section": sec,
                "group": camp_slug,
                "groupLabel": grp_lbl,
                "orderNum": order_counter,
            })
            order_counter += 1
            sec_count += 1

        if sec_count:
            active_tabs.append((sec, f"{tab_title} ({sec_count})"))

    tabs_html = [f'<button class="tab active" id="tab_all" onclick="setTab(\'all\')">Todas (<span id="tabCntAll">{len(all_new)}</span>)</button>']
    for sec, label in active_tabs:
        tabs_html.append(f'<button class="tab" id="tab_{sec}" onclick="setTab(\'{sec}\')">{label}</button>')
    tabs_html.append('<button class="tab" id="tab_old" onclick="setTab(\'old\')">✅ Aprobadas Anteriores (<span id="tabCntOld">0</span>)</button>')
    tabs_markup = "\n        ".join(tabs_html)

    tab_keys_js = json.dumps(["all"] + [sec for sec, _ in active_tabs] + ["old"])
    v2_prefixes_js = json.dumps([f"{c[0]}/" for c in CAMPAIGN_SPECS])

    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>NALU · Revisión V2 ({len(all_new)} Nuevas + Aprobadas)</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0d10;
      --panel: #13171f;
      --card: #161b24;
      --border: #252c38;
      --ink: #f2f5f8;
      --muted: #8d97a7;
      --accent: #86bcba;
      --keep: #5ce0a8;
      --improve: #f5c26b;
      --remove: #ff8a93;
      --wa: #25d366;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--ink);
      padding: 18px 16px 72px;
    }}
    .wrap {{ max-width: 1580px; margin: 0 auto; }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 14px;
      margin-bottom: 12px;
    }}
    h1 {{ margin: 0; font-size: 1.35rem; letter-spacing: 0.03em; }}
    .sub {{ color: var(--muted); font-size: 0.87rem; margin-top: 4px; }}
    .summary-pill {{
      display: inline-flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      margin-top: 8px;
    }}
    .notice {{
      background: #121a21;
      border: 1px solid rgba(134, 188, 186, 0.35);
      color: #d6e4e3;
      border-radius: 10px;
      padding: 10px 13px;
      font-size: 0.82rem;
      margin-bottom: 12px;
      line-height: 1.4;
    }}
    .header-actions {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .name-input {{
      background: var(--panel);
      color: var(--ink);
      border: 1px solid var(--accent);
      border-radius: 9px;
      padding: 8px 11px;
      font-size: 0.85rem;
      min-width: 170px;
      outline: none;
    }}
    .btn {{
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--ink);
      padding: 8px 12px;
      border-radius: 9px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .btn:hover {{ border-color: var(--accent); }}
    .btn.primary {{ background: var(--accent); color: #091515; border-color: var(--accent); }}
    .btn.wa {{ background: #143322; color: var(--wa); border-color: rgba(37, 211, 102, 0.55); }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }}
    .tab {{
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--muted);
      padding: 7px 13px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
    }}
    .tab.active {{ background: #182a2a; color: var(--accent); border-color: var(--accent); }}
    .controls {{
      position: sticky;
      top: 0;
      z-index: 20;
      background: rgba(11, 13, 16, 0.96);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 10px 0 12px;
      margin-bottom: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .row-controls {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    select, input[type="search"] {{
      background: var(--panel);
      color: var(--ink);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 8px 10px;
      font-size: 0.83rem;
      outline: none;
    }}
    input[type="search"] {{ min-width: 170px; flex: 1; max-width: 260px; }}
    .status-line {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      font-size: 0.8rem;
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
      gap: 15px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .card.st-keep {{ border-color: rgba(92, 224, 168, 0.65); }}
    .card.st-improve {{ border-color: rgba(245, 194, 107, 0.75); }}
    .card.st-remove {{ border-color: rgba(255, 138, 147, 0.78); }}
    .thumb-wrap {{
      position: relative;
      background: #07090b;
      aspect-ratio: 3 / 4;
      overflow: hidden;
      cursor: pointer;
    }}
    .thumb-wrap img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .idx-pill {{
      position: absolute; top: 8px; left: 8px;
      background: rgba(11, 13, 16, 0.85); color: #fff;
      font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.14);
    }}
    .grp-pill {{
      position: absolute; bottom: 8px; left: 8px;
      background: rgba(11, 13, 16, 0.86); color: var(--accent);
      font-size: 0.69rem; font-weight: 700; padding: 3px 8px; border-radius: 999px;
      border: 1px solid rgba(134, 188, 186, 0.35);
    }}
    .grp-pill.old {{ color: var(--keep); border-color: rgba(92, 224, 168, 0.35); }}
    .mark-pill {{
      position: absolute; top: 8px; right: 8px;
      font-size: 0.71rem; font-weight: 700; padding: 3px 8px; border-radius: 999px;
    }}
    .mark-pill.keep {{ background: #143828; color: var(--keep); }}
    .mark-pill.improve {{ background: #3b2d12; color: var(--improve); }}
    .mark-pill.remove {{ background: #3b171c; color: var(--remove); }}
    .meta {{ padding: 11px 12px 12px; display: flex; flex-direction: column; gap: 7px; flex: 1; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .badge {{
      font-size: 0.67rem; text-transform: uppercase; letter-spacing: 0.04em;
      padding: 2px 7px; border-radius: 999px; background: #1d2430; color: var(--accent); font-weight: 600;
    }}
    .badge.vw {{ color: #b7c2d2; background: #191e27; }}
    h3 {{ margin: 0; font-size: 0.9rem; line-height: 1.3; }}
    .sid {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.7rem; color: var(--muted); word-break: break-all; }}
    .rev-checks {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 2px; }}
    .chk-lbl {{
      display: flex; align-items: center; justify-content: center; gap: 5px;
      padding: 6px 4px; border-radius: 8px; border: 1px solid var(--border);
      background: #10141c; font-size: 0.76rem; font-weight: 600; cursor: pointer; user-select: none;
    }}
    .chk-lbl input {{ accent-color: var(--accent); margin: 0; cursor: pointer; }}
    .chk-lbl.active-keep {{ background: #143828; border-color: var(--keep); color: var(--keep); }}
    .chk-lbl.active-improve {{ background: #3b2d12; border-color: var(--improve); color: var(--improve); }}
    .chk-lbl.active-remove {{ background: #3b171c; border-color: var(--remove); color: var(--remove); }}
    .cmt-box {{
      width: 100%; background: #0d1118; color: var(--ink); border: 1px solid var(--border);
      border-radius: 8px; padding: 7px 9px; font-family: inherit; font-size: 0.79rem;
      line-height: 1.35; resize: vertical; min-height: 44px; outline: none;
    }}
    .lb {{
      position: fixed; inset: 0; z-index: 100; background: rgba(7, 9, 12, 0.98);
      display: none; flex-direction: column; padding: 10px 14px;
    }}
    .lb.open {{ display: flex; }}
    .lb-top {{
      display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
      padding-bottom: 8px; border-bottom: 1px solid var(--border);
    }}
    .lb-title {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }}
    .lb-counter {{
      font-size: 0.9rem; font-weight: 700; color: var(--accent);
      background: #132224; padding: 4px 10px; border-radius: 999px;
    }}
    .lb-name {{ font-size: 0.95rem; font-weight: 600; }}
    .lb-file {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 0.74rem; color: var(--muted); }}
    .lb-body {{ flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 330px; gap: 14px; padding: 10px 0; }}
    @media (max-width: 920px) {{
      .lb-body {{ grid-template-columns: 1fr; grid-template-rows: minmax(220px, 1fr) auto; overflow-y: auto; }}
      .lb-stage {{ padding: 0 42px; }}
      .lb-stage img {{ max-height: 52vh !important; }}
      .lb-side .rev-checks {{ grid-template-columns: repeat(3, 1fr) !important; }}
      .lb-side textarea {{ min-height: 64px !important; }}
    }}
    .lb-stage {{
      min-height: 0; display: flex; align-items: center; justify-content: center;
      position: relative; padding: 0 50px; touch-action: pan-y;
    }}
    .lb-stage img {{
      max-width: 100%; max-height: 73vh; object-fit: contain; border-radius: 10px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.65); user-select: none;
    }}
    .nav-btn {{
      position: absolute; top: 50%; transform: translateY(-50%);
      width: 42px; height: 54px; border-radius: 12px; border: 1px solid var(--border);
      background: rgba(20, 24, 32, 0.9); color: #fff; font-size: 1.4rem;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
    }}
    .nav-btn.prev {{ left: 2px; }}
    .nav-btn.next {{ right: 2px; }}
    .lb-side {{
      background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
      padding: 12px; display: flex; flex-direction: column; gap: 9px; overflow-y: auto;
    }}
    .lb-side h4 {{ margin: 0; font-size: 0.88rem; color: var(--ink); }}
    .lb-side .rev-checks {{ grid-template-columns: 1fr; gap: 7px; }}
    .lb-side .chk-lbl {{ justify-content: flex-start; padding: 8px 10px; font-size: 0.84rem; }}
    .lb-side textarea {{ min-height: 92px; font-size: 0.84rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .chip {{
      border: 1px solid var(--border); background: #0e1219; color: #cbd5e1;
      border-radius: 999px; padding: 4px 8px; font-size: 0.72rem; cursor: pointer;
    }}
    .chip:hover {{ border-color: var(--accent); color: var(--accent); }}
    .lb-strip {{
      display: flex; gap: 6px; overflow-x: auto; padding: 8px 4px 2px;
      border-top: 1px solid var(--border); scrollbar-width: thin;
    }}
    .strip-item {{
      flex: 0 0 auto; width: 46px; height: 60px; border-radius: 6px; overflow: hidden;
      border: 2px solid transparent; cursor: pointer; opacity: 0.55; background: #0d1015;
    }}
    .strip-item.active {{ border-color: var(--accent); opacity: 1; }}
    .strip-item.st-keep {{ border-color: var(--keep); }}
    .strip-item.st-improve {{ border-color: var(--improve); }}
    .strip-item.st-remove {{ border-color: var(--remove); }}
    .strip-item img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>NALU · Revisión V2 ({len(all_new)} Fotos Nuevas + Aprobadas)</h1>
        <div class="sub">Todas las correcciones, selector 7×4 y nuevas olas editoriales listas para revisar con <strong>Dejar / Mejorar / Quitar</strong>.</div>
        <div class="summary-pill">
          <span style="color:var(--keep)">✅ Dejar: <strong id="cntKeep">0</strong></span>
          <span style="color:var(--improve)">🔧 Mejorar: <strong id="cntImprove">0</strong></span>
          <span style="color:var(--remove)">🗑️ Quitar: <strong id="cntRemove">0</strong></span>
          <span style="color:var(--muted)">⏳ Pendientes: <strong id="cntPending">{len(all_new)}</strong></span>
        </div>
      </div>
      <div class="header-actions">
        <input type="text" class="name-input" id="reviewerName" placeholder="👤 Tu nombre (ej: Ana)" oninput="saveName(this.value)" />
        <button class="btn primary" onclick="openLightbox(0)">▶ Ver una por una</button>
        <button class="btn wa" onclick="sendWhatsApp()">💬 Enviar por WhatsApp</button>
        <button class="btn" onclick="copyReport()">📋 Copiar</button>
        <button class="btn" onclick="downloadJson()">📥 Descargar .json Completo</button>
        <label class="btn" style="display:inline-flex;align-items:center;gap:5px;">
          📂 Cargar .json
          <input type="file" accept=".json" onchange="uploadJson(event)" style="display:none;" />
        </label>
      </div>
    </header>

    <div class="notice" id="infoBanner"></div>

    <section class="controls">
      <div class="tabs">
        {tabs_markup}
      </div>
      <div class="row-controls">
        <select id="sortBy" onchange="applyState()">
          <option value="new_first">Ordenar: Más Nuevas Primero</option>
          <option value="color">Ordenar: Por Color (7 colores)</option>
        </select>
        <select id="filterView" onchange="applyState()">
          <option value="all">Vista: Todas</option>
          <option value="frente">Solo Frente</option>
          <option value="espalda">Solo Espalda</option>
        </select>
        <select id="filterColor" onchange="applyState()">
          <option value="all">Color: Todos</option>
          <option value="aguamarina">Aguamarina</option>
          <option value="blanco">Blanco</option>
          <option value="arcilla">Arcilla</option>
          <option value="carbon">Carbón</option>
          <option value="arena">Arena</option>
          <option value="laguna">Laguna</option>
          <option value="chocolate">Chocolate</option>
          <option value="duo">Dúo / Multi</option>
        </select>
        <select id="filterReview" onchange="applyState()">
          <option value="all">Estado: Todos</option>
          <option value="pending">Pendientes</option>
          <option value="keep">✅ Dejar</option>
          <option value="improve">🔧 Mejorar</option>
          <option value="remove">🗑️ Quitar</option>
          <option value="commented">💬 Con comentario</option>
        </select>
        <input type="search" id="searchBox" placeholder="Buscar foto o comentario..." oninput="applyState()" />
        <button class="btn" onclick="resetFilters()">Limpiar</button>
      </div>
      <div class="status-line">
        <span id="statusText">Mostrando {len(all_new)} de {len(all_new)} fotos</span>
        <span>Celular: desliza <strong>← / →</strong> en visor · PC: flechas <strong>← / →</strong>, <strong>1</strong> Dejar, <strong>2</strong> Mejorar, <strong>3</strong> Quitar.</span>
      </div>
    </section>

    <main class="grid" id="grid"></main>
  </div>

  <div class="lb" id="lightbox" role="dialog" aria-modal="true">
    <div class="lb-top">
      <div class="lb-title">
        <span class="lb-counter" id="lbCounter">1 / {len(all_new)}</span>
        <div>
          <div class="lb-name" id="lbName"></div>
          <div class="lb-file" id="lbFile"></div>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn wa" onclick="sendWhatsApp()">💬 Enviar WhatsApp</button>
        <button class="btn" onclick="copyReport()">📋 Copiar</button>
        <button class="btn" onclick="closeLightbox()">✕ Cerrar</button>
      </div>
    </div>

    <div class="lb-body">
      <div class="lb-stage" id="lbStage">
        <button class="nav-btn prev" onclick="stepLightbox(-1)" title="Anterior (←)">‹</button>
        <img id="lbImg" src="" alt="" />
        <button class="nav-btn next" onclick="stepLightbox(1)" title="Siguiente (→)">›</button>
      </div>

      <aside class="lb-side">
        <h4>Selección de revisión</h4>
        <div class="rev-checks">
          <label class="chk-lbl" id="lbChkKeep">
            <input type="checkbox" id="lbInKeep" onchange="setStatusCurrent('keep')" />
            <span>✅ Dejar (1)</span>
          </label>
          <label class="chk-lbl" id="lbChkImprove">
            <input type="checkbox" id="lbInImprove" onchange="setStatusCurrent('improve')" />
            <span>🔧 Mejorar (2)</span>
          </label>
          <label class="chk-lbl" id="lbChkRemove">
            <input type="checkbox" id="lbInRemove" onchange="setStatusCurrent('remove')" />
            <span>🗑️ Quitar (3)</span>
          </label>
        </div>

        <h4>Comentario</h4>
        <textarea class="cmt-box" id="lbComment" placeholder="Ej: nudos en puntas, tanga más metida, top cortina..." oninput="setCommentCurrent(this.value)"></textarea>

        <div>
          <div style="font-size:0.74rem;color:var(--muted);margin-bottom:5px;">Etiquetas rápidas (clic para agregar):</div>
          <div class="chips">
            <button type="button" class="chip" onclick="appendChip('nudos en puntas')">+ nudos en puntas</button>
            <button type="button" class="chip" onclick="appendChip('tanga más metida')">+ tanga más metida</button>
            <button type="button" class="chip" onclick="appendChip('top cortina')">+ top cortina</button>
            <button type="button" class="chip" onclick="appendChip('costura')">+ costura</button>
            <button type="button" class="chip" onclick="appendChip('piel')">+ piel</button>
            <button type="button" class="chip" onclick="appendChip('manos/pies')">+ manos/pies</button>
          </div>
        </div>
      </aside>
    </div>

    <div class="lb-strip" id="lbStrip"></div>
  </div>

  <script>
    const NEW_ITEMS = {json.dumps(all_new, ensure_ascii=False)};
    const OLD_ITEMS = {json.dumps(old_items, ensure_ascii=False)};
    const TAB_KEYS = {tab_keys_js};
    const V2_PREFIXES = {v2_prefixes_js};
    const STORAGE_V1 = 'nalu_public_review_v1';
    const STORAGE_V2 = 'nalu_public_review_v2';
    const STORAGE_NAME = 'nalu_public_reviewer_v1';

    let v1Reviews = {{}};
    let v2Reviews = {{}};
    let reviewerName = '';
    try {{
      v1Reviews = JSON.parse(localStorage.getItem(STORAGE_V1) || '{{}}');
      v2Reviews = JSON.parse(localStorage.getItem(STORAGE_V2) || '{{}}');
      reviewerName = localStorage.getItem(STORAGE_NAME) || '';
    }} catch (e) {{
      v1Reviews = {{}};
      v2Reviews = {{}};
      reviewerName = '';
    }}
    document.getElementById('reviewerName').value = reviewerName;

    let activeTab = 'all';
    let filtered = [];
    let currentIdx = 0;

    function getApprovedOldItems() {{
      return OLD_ITEMS
        .filter(it => v1Reviews[it.origSrc] && v1Reviews[it.origSrc].status === 'keep')
        .map((it, idx) => ({{
          ...it,
          isNew: false,
          section: 'old',
          group: 'approved_old',
          groupLabel: 'Aprobada Anterior',
          orderNum: 10000 + idx,
        }}));
    }}

    function getPool() {{
      return [...NEW_ITEMS, ...getApprovedOldItems()];
    }}

    function getRev(it) {{
      if (v2Reviews[it.origSrc]) return v2Reviews[it.origSrc];
      if (!it.isNew && v1Reviews[it.origSrc]) {{
        return {{ status: v1Reviews[it.origSrc].status || '', comment: v1Reviews[it.origSrc].comment || '' }};
      }}
      return {{ status: '', comment: '' }};
    }}

    function saveName(val) {{
      reviewerName = val.trim();
      try {{ localStorage.setItem(STORAGE_NAME, reviewerName); }} catch (e) {{}}
    }}

    function saveV2() {{
      try {{ localStorage.setItem(STORAGE_V2, JSON.stringify(v2Reviews)); }} catch (e) {{}}
      updateCounts();
    }}

    function setTab(t) {{
      activeTab = t;
      TAB_KEYS.forEach(k => {{
        const el = document.getElementById('tab_' + k);
        if (el) el.classList.toggle('active', t === k);
      }});
      applyState();
    }}

    function updateCounts() {{
      const oldList = getApprovedOldItems();
      const pool = [...NEW_ITEMS, ...oldList];
      let keep = 0, improve = 0, remove = 0;
      pool.forEach(it => {{
        const st = getRev(it).status;
        if (st === 'keep') keep++;
        else if (st === 'improve') improve++;
        else if (st === 'remove') remove++;
      }});
      const pending = pool.length - (keep + improve + remove);
      document.getElementById('cntKeep').textContent = keep;
      document.getElementById('cntImprove').textContent = improve;
      document.getElementById('cntRemove').textContent = remove;
      document.getElementById('cntPending').textContent = pending;
      document.getElementById('tabCntAll').textContent = pool.length;
      document.getElementById('tabCntOld').textContent = oldList.length;

      const banner = document.getElementById('infoBanner');
      if (oldList.length === 0) {{
        banner.innerHTML = `ℹ️ Estás viendo las <strong>${{NEW_ITEMS.length}} fotos nuevas</strong>. Si abres este enlace desde el <strong>mismo celular/navegador</strong> donde aprobaste las 43 anteriores, aparecerán aquí automáticamente — o puedes cargarlas con <strong>📂 Cargar .json</strong>.`;
      }} else {{
        banner.innerHTML = `✅ Se cargaron automáticamente <strong>${{oldList.length}} fotos aprobadas</strong> de tu revisión anterior + las <strong>${{NEW_ITEMS.length}} fotos nuevas</strong> (${{pool.length}} en total).`;
      }}
    }}

    function escHtml(s) {{
      return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }}

    function sortItems(list, mode) {{
      const arr = [...list];
      arr.sort((a, b) => {{
        if (mode === 'color') {{
          return a.colorRank - b.colorRank || (a.isNew === b.isNew ? 0 : a.isNew ? -1 : 1) || a.orderNum - b.orderNum;
        }}
        return (a.isNew === b.isNew ? 0 : a.isNew ? -1 : 1) || b.orderNum - a.orderNum;
      }});
      return arr;
    }}

    function applyState() {{
      const pool = getPool();
      const sortMode = document.getElementById('sortBy').value;
      const vw = document.getElementById('filterView').value;
      const col = document.getElementById('filterColor').value;
      const revF = document.getElementById('filterReview').value;
      const q = document.getElementById('searchBox').value.trim().toLowerCase();

      const base = pool.filter(it => {{
        if (activeTab !== 'all' && it.section !== activeTab) return false;
        if (vw !== 'all' && it.view !== vw) return false;
        if (col !== 'all' && it.color !== col) return false;
        const rv = getRev(it);
        if (revF === 'pending' && rv.status !== '') return false;
        if (revF === 'keep' && rv.status !== 'keep') return false;
        if (revF === 'improve' && rv.status !== 'improve') return false;
        if (revF === 'remove' && rv.status !== 'remove') return false;
        if (revF === 'commented' && !rv.comment.trim()) return false;
        if (q) {{
          const hay = `${{it.name}} ${{it.file}} ${{it.colorLabel}} ${{it.groupLabel}} ${{rv.comment}}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }}
        return true;
      }});

      filtered = sortItems(base, sortMode);
      renderGrid(pool.length);
      updateCounts();
    }}

    function renderGrid(totalPool) {{
      const grid = document.getElementById('grid');
      document.getElementById('statusText').textContent = `Mostrando ${{filtered.length}} de ${{totalPool}} fotos`;
      grid.innerHTML = filtered.map((it, idx) => {{
        const rv = getRev(it);
        const stCls = rv.status ? `st-${{rv.status}}` : '';
        const pillMap = {{
          keep: '<span class="mark-pill keep">✅ Dejar</span>',
          improve: '<span class="mark-pill improve">🔧 Mejorar</span>',
          remove: '<span class="mark-pill remove">🗑️ Quitar</span>',
        }};
        const badgeSt = pillMap[rv.status] || '';
        const safeKey = escHtml(it.origSrc);
        const safeImg = escHtml(it.src);
        const safeCmt = escHtml(rv.comment);
        const grpCls = it.isNew ? 'grp-pill' : 'grp-pill old';
        return `
          <article class="card ${{stCls}}" data-key="${{safeKey}}">
            <div class="thumb-wrap" onclick="openLightbox(${{idx}})">
              <img src="${{safeImg}}" alt="${{escHtml(it.name)}}" loading="lazy" />
              <span class="idx-pill">#${{idx + 1}}</span>
              <span class="${{grpCls}}">${{escHtml(it.groupLabel)}}</span>
              ${{badgeSt}}
            </div>
            <div class="meta">
              <div class="badges">
                <span class="badge">${{escHtml(it.colorLabel)}}</span>
                <span class="badge vw">${{escHtml(it.viewLabel)}}</span>
              </div>
              <h3>${{escHtml(it.name)}}</h3>
              <div class="sid">${{escHtml(it.file)}}</div>
              <div class="rev-checks" onclick="event.stopPropagation()">
                <label class="chk-lbl ${{rv.status === 'keep' ? 'active-keep' : ''}}">
                  <input type="checkbox" ${{rv.status === 'keep' ? 'checked' : ''}} onchange="setCardStatus('${{safeKey}}', 'keep', this.closest('.card'))" />
                  <span>Dejar</span>
                </label>
                <label class="chk-lbl ${{rv.status === 'improve' ? 'active-improve' : ''}}">
                  <input type="checkbox" ${{rv.status === 'improve' ? 'checked' : ''}} onchange="setCardStatus('${{safeKey}}', 'improve', this.closest('.card'))" />
                  <span>Mejorar</span>
                </label>
                <label class="chk-lbl ${{rv.status === 'remove' ? 'active-remove' : ''}}">
                  <input type="checkbox" ${{rv.status === 'remove' ? 'checked' : ''}} onchange="setCardStatus('${{safeKey}}', 'remove', this.closest('.card'))" />
                  <span>Quitar</span>
                </label>
              </div>
              <textarea class="cmt-box" placeholder="¿Por qué? (ej: nudos, tanga más metida, top...)" onclick="event.stopPropagation()" oninput="setCardComment('${{safeKey}}', this.value)">${{safeCmt}}</textarea>
            </div>
          </article>
        `;
      }}).join('');
    }}

    function findItemByKey(key) {{
      return getPool().find(x => x.origSrc === key);
    }}

    function updateReview(key, patch) {{
      const it = findItemByKey(key);
      const cur = it ? getRev(it) : (v2Reviews[key] || {{ status: '', comment: '' }});
      const next = {{ status: cur.status, comment: cur.comment, ...patch }};
      if (!next.status && !next.comment.trim() && (!it || it.isNew)) {{
        delete v2Reviews[key];
      }} else {{
        v2Reviews[key] = next;
      }}
      saveV2();
    }}

    function setCardStatus(key, targetStatus, cardEl) {{
      const it = findItemByKey(key);
      const cur = it ? getRev(it).status : '';
      const nextStatus = cur === targetStatus ? '' : targetStatus;
      updateReview(key, {{ status: nextStatus }});
      const labels = cardEl.querySelectorAll('.chk-lbl');
      const inputs = cardEl.querySelectorAll('.chk-lbl input');
      const statuses = ['keep', 'improve', 'remove'];
      cardEl.className = 'card' + (nextStatus ? ` st-${{nextStatus}}` : '');
      labels.forEach((lbl, i) => {{
        const st = statuses[i];
        lbl.className = 'chk-lbl' + (nextStatus === st ? ` active-${{st}}` : '');
        inputs[i].checked = (nextStatus === st);
      }});
      const thumb = cardEl.querySelector('.thumb-wrap');
      const oldPill = thumb.querySelector('.mark-pill');
      if (oldPill) oldPill.remove();
      if (nextStatus) {{
        const pillTxt = {{ keep: '✅ Dejar', improve: '🔧 Mejorar', remove: '🗑️ Quitar' }}[nextStatus];
        const span = document.createElement('span');
        span.className = `mark-pill ${{nextStatus}}`;
        span.textContent = pillTxt;
        thumb.appendChild(span);
      }}
    }}

    function setCardComment(key, text) {{
      updateReview(key, {{ comment: text }});
    }}

    function resetFilters() {{
      setTab('all');
      document.getElementById('filterView').value = 'all';
      document.getElementById('filterColor').value = 'all';
      document.getElementById('filterReview').value = 'all';
      document.getElementById('searchBox').value = '';
      applyState();
    }}

    function openLightbox(idx) {{
      if (!filtered.length) return;
      currentIdx = Math.max(0, Math.min(idx, filtered.length - 1));
      document.getElementById('lightbox').classList.add('open');
      renderStrip();
      showCurrent();
    }}

    function closeLightbox() {{
      document.getElementById('lightbox').classList.remove('open');
      applyState();
    }}

    function stepLightbox(delta) {{
      if (!filtered.length) return;
      currentIdx = (currentIdx + delta + filtered.length) % filtered.length;
      showCurrent();
    }}

    function showCurrent() {{
      const it = filtered[currentIdx];
      const rv = getRev(it);
      document.getElementById('lbCounter').textContent = `${{currentIdx + 1}} / ${{filtered.length}}`;
      document.getElementById('lbName').textContent = it.name;
      document.getElementById('lbFile').textContent = `${{it.groupLabel}} · ${{it.colorLabel}} · ${{it.viewLabel}} · ${{it.file}}`;
      const img = document.getElementById('lbImg');
      img.src = it.src;
      img.alt = it.name;
      document.getElementById('lbComment').value = rv.comment || '';
      syncLightboxChecks(rv.status);
      document.querySelectorAll('.strip-item').forEach((el, i) => {{
        const sit = filtered[i];
        const sst = sit ? getRev(sit).status : '';
        el.className = 'strip-item' + (i === currentIdx ? ' active' : '') + (sst ? ` st-${{sst}}` : '');
        if (i === currentIdx) el.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
      }});
    }}

    function syncLightboxChecks(st) {{
      [['keep', 'lbChkKeep', 'lbInKeep'], ['improve', 'lbChkImprove', 'lbInImprove'], ['remove', 'lbChkRemove', 'lbInRemove']].forEach(([key, lblId, inId]) => {{
        document.getElementById(lblId).className = 'chk-lbl' + (st === key ? ` active-${{key}}` : '');
        document.getElementById(inId).checked = (st === key);
      }});
    }}

    function setStatusCurrent(targetStatus) {{
      const it = filtered[currentIdx];
      if (!it) return;
      const cur = getRev(it).status;
      const nextStatus = cur === targetStatus ? '' : targetStatus;
      updateReview(it.origSrc, {{ status: nextStatus }});
      syncLightboxChecks(nextStatus);
      const stripEl = document.querySelectorAll('.strip-item')[currentIdx];
      if (stripEl) stripEl.className = 'strip-item active' + (nextStatus ? ` st-${{nextStatus}}` : '');
    }}

    function setCommentCurrent(text) {{
      const it = filtered[currentIdx];
      if (!it) return;
      updateReview(it.origSrc, {{ comment: text }});
    }}

    function appendChip(tag) {{
      const it = filtered[currentIdx];
      if (!it) return;
      const ta = document.getElementById('lbComment');
      const cur = ta.value.trim();
      const next = cur ? (cur.includes(tag) ? cur : `${{cur}}; ${{tag}}`) : tag;
      ta.value = next;
      updateReview(it.origSrc, {{ comment: next }});
      if (!getRev(it).status) setStatusCurrent('improve');
    }}

    function renderStrip() {{
      const strip = document.getElementById('lbStrip');
      strip.innerHTML = filtered.map((it, i) => {{
        const st = getRev(it).status;
        const stCls = st ? ` st-${{st}}` : '';
        return `<div class="strip-item${{stCls}}" onclick="currentIdx=${{i}};showCurrent()" title="#${{i+1}} ${{escHtml(it.file)}}"><img src="${{escHtml(it.src)}}" loading="lazy" /></div>`;
      }}).join('');
    }}

    function gatherStats() {{
      const keeps = [], improves = [], removes = [];
      getPool().forEach(it => {{
        const rv = getRev(it);
        if (rv.status === 'improve') improves.push({{ ...it, comment: rv.comment.trim() }});
        else if (rv.status === 'remove') removes.push({{ ...it, comment: rv.comment.trim() }});
        else if (rv.status === 'keep') keeps.push({{ ...it, comment: rv.comment.trim() }});
        else if (rv.comment.trim()) improves.push({{ ...it, comment: rv.comment.trim() }});
      }});
      return {{ keeps, improves, removes }};
    }}

    function buildReportText() {{
      const {{ keeps, improves, removes }} = gatherStats();
      if (!improves.length && !removes.length && !keeps.length) return '';
      const who = reviewerName || 'Socia / Equipo NALU';
      const lines = [
        `REVISIÓN NALU V2 — ${{who}}`,
        `Dejar: ${{keeps.length}} | Mejorar: ${{improves.length}} | Quitar: ${{removes.length}}`,
        ''
      ];
      if (improves.length) {{
        lines.push(`MEJORAR (${{improves.length}}):`);
        improves.forEach(x => lines.push(`🔧 ${{x.file}}: ${{x.comment || ''}}`));
        lines.push('');
      }}
      if (removes.length) {{
        lines.push(`QUITAR (${{removes.length}}):`);
        removes.forEach(x => lines.push(`🗑️ ${{x.file}}: ${{x.comment || ''}}`));
        lines.push('');
      }}
      if (keeps.length) {{
        lines.push(`DEJAR (${{keeps.length}}):`);
        keeps.forEach(x => lines.push(`✅ ${{x.file}}${{x.comment ? ': ' + x.comment : ''}}`));
      }}
      return lines.join('\\n');
    }}

    function copyReport() {{
      const text = buildReportText();
      if (!text) {{ alert('Aún no has marcado ninguna foto.'); return; }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(() => alert('Reporte copiado al portapapeles.'));
      }} else {{
        prompt('Copia este reporte:', text);
      }}
    }}

    function sendWhatsApp() {{
      const fullText = buildReportText();
      if (!fullText) {{ alert('Aún no has marcado ninguna foto.'); return; }}
      const {{ keeps, improves, removes }} = gatherStats();
      const who = reviewerName || 'Socia / Equipo NALU';
      let waText = fullText;
      if (encodeURIComponent(fullText).length > 3500) {{
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(fullText).catch(() => {{}});
        }}
        const shortLines = [
          `REVISIÓN NALU V2 — ${{who}}`,
          `Dejar: ${{keeps.length}} | Mejorar: ${{improves.length}} | Quitar: ${{removes.length}}`,
          '',
          ...improves.slice(0, 15).map(x => `🔧 ${{x.file}}: ${{x.comment || ''}}`),
          ...removes.slice(0, 10).map(x => `🗑️ ${{x.file}}: ${{x.comment || ''}}`),
          '',
          '(Lista completa copiada — también puedes tocar Descargar .json Completo)'
        ];
        waText = shortLines.join('\\n');
        alert('Tu lista es larga: se copió completa al portapapeles y ahora se abrirá WhatsApp con el resumen.');
      }}
      window.open(`https://wa.me/?text=${{encodeURIComponent(waText)}}`, '_blank', 'noopener');
    }}

    function downloadJson() {{
      const whoRaw = (reviewerName || 'socia').toLowerCase().replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'socia';
      const cleanV1 = Object.fromEntries(Object.entries(v1Reviews).filter(([_, v]) => v && (v.status || (v.comment && v.comment.trim()))));
      const cleanV2 = Object.fromEntries(Object.entries(v2Reviews).filter(([_, v]) => v && (v.status || (v.comment && v.comment.trim()))));
      const payload = {{
        reviewer: reviewerName || 'Socia / Equipo NALU',
        updated_at: new Date().toISOString(),
        source: 'nalu-revision-v2',
        total_v1: OLD_ITEMS.length,
        total_v2: NEW_ITEMS.length,
        reviews_v2: cleanV2,
        reviews_v1: cleanV1,
        reviews: {{ ...cleanV1, ...cleanV2 }},
      }};
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nalu_revision_v2_completo_${{whoRaw}}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }}

    function uploadJson(event) {{
      const f = event.target.files && event.target.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          const parsed = JSON.parse(reader.result);
          if (parsed.reviewer) {{
            reviewerName = String(parsed.reviewer);
            document.getElementById('reviewerName').value = reviewerName;
            saveName(reviewerName);
          }}
          if (parsed.reviews_v1 || parsed.reviews_v2) {{
            if (parsed.reviews_v1) v1Reviews = parsed.reviews_v1;
            if (parsed.reviews_v2) v2Reviews = parsed.reviews_v2;
          }} else {{
            const incoming = parsed.reviews || parsed;
            if (typeof incoming === 'object' && incoming) {{
              Object.entries(incoming).forEach(([k, v]) => {{
                if (V2_PREFIXES.some(p => k.startsWith(p))) v2Reviews[k] = v;
                else v1Reviews[k] = v;
              }});
            }}
          }}
          try {{
            localStorage.setItem(STORAGE_V1, JSON.stringify(v1Reviews));
            localStorage.setItem(STORAGE_V2, JSON.stringify(v2Reviews));
          }} catch (e) {{}}
          applyState();
          alert('Revisión cargada correctamente.');
        }} catch (err) {{
          alert('No se pudo leer el archivo JSON.');
        }}
      }};
      reader.readAsText(f);
      event.target.value = '';
    }}

    let touchX = null;
    let touchY = null;
    const stageEl = document.getElementById('lbStage');
    stageEl.addEventListener('touchstart', (e) => {{
      if (e.touches && e.touches.length === 1) {{
        touchX = e.touches[0].clientX;
        touchY = e.touches[0].clientY;
      }}
    }}, {{ passive: true }});
    stageEl.addEventListener('touchend', (e) => {{
      if (touchX === null || !e.changedTouches || !e.changedTouches.length) return;
      const dx = e.changedTouches[0].clientX - touchX;
      const dy = e.changedTouches[0].clientY - touchY;
      touchX = null;
      touchY = null;
      if (Math.abs(dx) >= 50 && Math.abs(dx) > Math.abs(dy) * 1.2) {{
        stepLightbox(dx < 0 ? 1 : -1);
      }}
    }}, {{ passive: true }});

    document.addEventListener('keydown', (e) => {{
      const lbOpen = document.getElementById('lightbox').classList.contains('open');
      if (!lbOpen) return;
      const tag = document.activeElement ? document.activeElement.tagName : '';
      if (tag === 'TEXTAREA' || tag === 'INPUT') {{
        if (e.key === 'Escape') document.activeElement.blur();
        return;
      }}
      if (e.key === 'ArrowRight') stepLightbox(1);
      else if (e.key === 'ArrowLeft') stepLightbox(-1);
      else if (e.key === '1') setStatusCurrent('keep');
      else if (e.key === '2') setStatusCurrent('improve');
      else if (e.key === '3') setStatusCurrent('remove');
      else if (e.key === 'Escape') closeLightbox();
    }});

    applyState();
  </script>
</body>
</html>
"""

    out_html = WEB_V2 / "index.html"
    out_html.write_text(html, encoding="utf-8")
    js_tmp = Path("/tmp/v2_builder_check.js")
    js_match = re.search(r"<script>(.*)</script>", html, re.S)
    js_tmp.write_text(js_match.group(1), encoding="utf-8")
    subprocess.run(["node", "--check", str(js_tmp)], check=True)
    js_tmp.unlink(missing_ok=True)
    print(f"build_v2_site OK: {len(all_new)} new items across {len(active_tabs)} tabs | {len(old_items)} old items pool")


if __name__ == "__main__":
    main()
