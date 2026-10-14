"""Embed the pipeline's row-level payload in the offline HTML dashboard."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build():
    payload = json.loads((ROOT / "reports/dashboard_data.json").read_text())
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Prevent source text from accidentally terminating the JSON script element.
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (ROOT / "dashboard/template.html").read_text()
    assert template.count("__DATA__") == 1
    target = ROOT / "dashboard/IRCTC_Dashboard.html"
    target.write_text(template.replace("__DATA__", text))
    print(f"Dashboard built with {len(payload['rows']):,} records: {target.name}")

if __name__ == "__main__":
    build()
