"""Standalone self-contained HTML audit report generator for WebAssembly binaries."""

from __future__ import annotations

import html
from typing import Optional

from wasmlens.cfg.analyzer import CFGAnalyzer
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.decompiler.reconstructor import Decompiler
from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
)
from wasmlens.parser.types import ExternalKind, WasmModule
from wasmlens.profiler.bloat import analyze_bloat


def generate_html_report(module: WasmModule, title: Optional[str] = "WasmLens Audit Report") -> str:
    """Generate self-contained HTML inspection and audit report."""
    bloat = analyze_bloat(module)
    decompiler = Decompiler(module)

    # Functions summary
    functions_html = []
    exports_map = {
        e.index: e.name
        for e in module.exports
        if e.kind == ExternalKind.FUNCTION
    }

    for f_idx in range(module.total_func_count):
        fn_name = module.get_function_name(f_idx)
        sig = module.get_function_type(f_idx).to_wat()
        exported = exports_map.get(f_idx, "-")
        is_imported = f_idx < module.imported_func_count

        wat_code = ""
        c_code = ""
        cfg_info = ""

        if not is_imported:
            try:
                wat_code = disassemble_function(module, f_idx)
            except Exception as e:
                wat_code = f";; Error disassembling: {e}"

            try:
                c_code = decompiler.decompile_function(f_idx)
            except Exception as e:
                c_code = f"// Error decompiling: {e}"

            try:
                builder = CFGBuilder(module)
                g = builder.build_cfg(f_idx)
                analyzer = CFGAnalyzer(g)
                metrics = analyzer.analyze()
                cfg_info = f"Blocks: {metrics.block_count} | Edges: {metrics.edge_count} | Cyclomatic Complexity: {metrics.cyclomatic_complexity}"
            except Exception:
                cfg_info = ""

        functions_html.append(
            f"""
            <div class="card fn-card">
              <div class="fn-header">
                <div>
                  <span class="badge">Func {f_idx}</span>
                  <span class="fn-name">${html.escape(fn_name)}</span>
                  <span class="sig">{html.escape(sig)}</span>
                </div>
                <div>
                  {f'<span class="badge export-badge">Export: {html.escape(exported)}</span>' if exported != "-" else ""}
                  {f'<span class="badge imported-badge">Imported</span>' if is_imported else ""}
                </div>
              </div>
              {f'<div class="cfg-meta">{html.escape(cfg_info)}</div>' if cfg_info else ""}
              {f'''
              <div class="code-grid">
                <div>
                  <div class="code-label">WAT Disassembly</div>
                  <pre class="code-block"><code>{html.escape(wat_code)}</code></pre>
                </div>
                <div>
                  <div class="code-label">Decompiled C Pseudocode</div>
                  <pre class="code-block"><code>{html.escape(c_code)}</code></pre>
                </div>
              </div>''' if not is_imported else '<div class="muted">External host function (no bytecode body)</div>'}
            </div>
            """
        )

    # Sections table rows
    sec_rows = []
    for s in module.sections:
        name = s.name if s.name else s.id.name.lower()
        sec_rows.append(
            f"<tr><td>{s.id.value}</td><td>{html.escape(name)}</td><td class='num'>{s.size:,} B</td><td class='hex'>0x{s.payload_offset:04X}</td></tr>"
        )

    # Bloat table rows
    bloat_rows = []
    for s in bloat.sections:
        bloat_rows.append(
            f"<tr><td>{html.escape(s.name)}</td><td class='num'>{s.size:,} B</td><td class='num'>{s.percentage:.1f}%</td></tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --accent-dim: #1f6feb;
      --green: #3fb950;
      --yellow: #d29922;
      --font-mono: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    h1 {{ font-size: 24px; color: #f0f6fc; font-weight: 600; display: flex; align-items: center; gap: 10px; }}
    .meta-pills {{ display: flex; gap: 8px; font-size: 13px; }}
    .badge {{
      background: #21262d;
      border: 1px solid var(--border);
      padding: 3px 8px;
      border-radius: 6px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-size: 12px;
    }}
    .export-badge {{ background: rgba(56, 139, 253, 0.15); color: var(--accent); border-color: rgba(56, 139, 253, 0.4); }}
    .imported-badge {{ background: rgba(210, 153, 34, 0.15); color: var(--yellow); border-color: rgba(210, 153, 34, 0.4); }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }}
    .stat-label {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
    .stat-value {{ font-size: 24px; font-weight: 600; color: #f0f6fc; margin-top: 4px; font-family: var(--font-mono); }}
    h2 {{ font-size: 18px; color: #f0f6fc; margin: 28px 0 12px; display: flex; align-items: center; gap: 8px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-bottom: 16px;
    }}
    th, td {{
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--text-muted); font-weight: 500; background: #0b0e14; }}
    .num {{ text-align: right; font-family: var(--font-mono); }}
    .hex {{ text-align: right; font-family: var(--font-mono); color: var(--text-muted); }}
    .fn-card {{ margin-bottom: 16px; }}
    .fn-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .fn-name {{ font-family: var(--font-mono); font-weight: 600; color: var(--accent); margin-left: 6px; }}
    .sig {{ font-family: var(--font-mono); color: var(--green); font-size: 13px; margin-left: 8px; }}
    .cfg-meta {{ font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); margin-bottom: 12px; }}
    .code-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 900px) {{ .code-grid {{ grid-template-columns: 1fr; }} }}
    .code-label {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 6px; letter-spacing: 0.5px; }}
    .code-block {{
      background: #090d13;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      font-family: var(--font-mono);
      font-size: 12px;
      overflow-x: auto;
      max-height: 400px;
      line-height: 1.45;
    }}
    .muted {{ color: var(--text-muted); font-size: 13px; }}
    footer {{
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid var(--border);
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>WasmLens Binary Report</h1>
        <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">WebAssembly 2.0 Module Static Analysis & Audit</div>
      </div>
      <div class="meta-pills">
        <span class="badge">Magic: {module.magic.decode('latin1', errors='replace')}</span>
        <span class="badge">Version: {module.version}</span>
      </div>
    </header>

    <div class="stats-grid">
      <div class="card">
        <div class="stat-label">Total Functions</div>
        <div class="stat-value">{module.total_func_count}</div>
      </div>
      <div class="card">
        <div class="stat-label">Binary Sections</div>
        <div class="stat-value">{len(module.sections)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Exported Symbols</div>
        <div class="stat-value">{len(module.exports)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Total Size</div>
        <div class="stat-value">{bloat.total_size:,} B</div>
      </div>
    </div>

    <h2>Binary Sections</h2>
    <div class="card" style="padding: 0; overflow: hidden;">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th class="num">Size</th>
            <th class="hex">Payload Offset</th>
          </tr>
        </thead>
        <tbody>
          {"".join(sec_rows)}
        </tbody>
      </table>
    </div>

    <h2>Binary Bloat Breakdown</h2>
    <div class="card" style="padding: 0; overflow: hidden;">
      <table>
        <thead>
          <tr>
            <th>Section</th>
            <th class="num">Size</th>
            <th class="num">Percentage</th>
          </tr>
        </thead>
        <tbody>
          {"".join(bloat_rows)}
        </tbody>
      </table>
    </div>

    <h2>Compiled Functions & Decompilation</h2>
    {"".join(functions_html)}

    <footer>
      Report generated by WasmLens &bull; WebAssembly 2.0 Binary Decompiler & Inspector
    </footer>
  </div>
</body>
</html>
"""
    return doc
