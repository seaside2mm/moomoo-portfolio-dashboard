from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "app" / "static"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist" / "frontend"


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def rewrite_index_for_static_host(index_html: str) -> str:
    return (
        index_html
        .replace('/static/styles.css?v=20260609-sync-fix1', 'styles.css?v=20260609-sync-fix1')
        .replace(
            '<script src="/static/dashboard.js?v=20260609-sync-fix1"></script>',
            '<script src="config.js?v=20260609-sync-fix1"></script>\n'
            '    <script src="dashboard.js?v=20260609-sync-fix1"></script>',
        )
    )


def build_frontend(
    output_dir: Path,
    api_base_url: str,
    read_only: bool,
    requires_write_token: bool = True,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(STATIC_DIR / "styles.css", output_dir / "styles.css")
    shutil.copy2(STATIC_DIR / "dashboard.js", output_dir / "dashboard.js")

    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    (output_dir / "index.html").write_text(rewrite_index_for_static_host(index_html), encoding="utf-8")

    config = {
        "apiBaseUrl": api_base_url.rstrip("/"),
        "readOnly": read_only,
        "requiresWriteToken": requires_write_token,
    }
    config_js = f"window.PORTFOLIO_DASHBOARD_CONFIG = {json.dumps(config, ensure_ascii=False, indent=2)};\n"
    (output_dir / "config.js").write_text(config_js, encoding="utf-8")

    # Avoid GitHub Pages/Jekyll treating underscored paths specially.
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static frontend assets for online deployment.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--read-only", default="true")
    parser.add_argument("--requires-write-token", default="true")
    args = parser.parse_args()

    build_frontend(
        output_dir=args.output_dir,
        api_base_url=args.api_base_url,
        read_only=parse_bool(args.read_only),
        requires_write_token=parse_bool(args.requires_write_token),
    )


if __name__ == "__main__":
    main()
