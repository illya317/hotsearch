#!/usr/bin/env python3
"""
Convert report JSON to static HTML using Jinja2 template.

Usage:
    python scripts/html_convert.py --input data/cache/summary/report_20260511_0148.json
    python scripts/html_convert.py                          # use latest report
    python scripts/html_convert.py --output out.html        # custom output path
"""

import argparse
import json
import sys
from pathlib import Path

import jinja2

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hotsearch import CACHE_SUMMARY_DIR, CONFIG_DIR, OUTPUT_DIR  # noqa: E402


def _find_latest_report() -> Path | None:
    """Find the most recent report_*.json in cache/summary."""
    candidates = []
    for path in CACHE_SUMMARY_DIR.glob("report_*.json"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except Exception:
            continue
    if not candidates:
        return None
    return sorted(candidates, reverse=True)[0][1]


def _default_output(input_path: Path) -> Path:
    """Derive default HTML output path into data/outputs/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / f"{input_path.stem}.html"


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert report JSON to HTML")
    ap.add_argument("--input", "-i", help="Path to report JSON (default: latest)")
    ap.add_argument("--output", "-o", help="Output HTML path (default: same name as input)")
    ap.add_argument(
        "--template",
        "-t",
        default=str(CONFIG_DIR / "templates" / "hotsearch.html"),
        help="Path to Jinja2 template",
    )
    args = ap.parse_args()

    # Resolve input
    if args.input:
        input_path = Path(args.input)
    else:
        input_path = _find_latest_report()
        if input_path is None:
            print("Error: no report JSON found in", CACHE_SUMMARY_DIR, file=sys.stderr)
            sys.exit(1)
            return

    if not input_path.exists():
        print("Error: input file not found:", input_path, file=sys.stderr)
        sys.exit(1)
        return

    # Resolve output
    output_path = Path(args.output) if args.output else _default_output(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve template
    template_path = Path(args.template)
    if not template_path.exists():
        print("Error: template not found:", template_path, file=sys.stderr)
        sys.exit(1)
        return

    # Load report data
    report = json.loads(input_path.read_text(encoding="utf-8"))

    # Render
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    template = jinja_env.get_template(template_path.name)
    html = template.render(report=report)

    output_path.write_text(html, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
