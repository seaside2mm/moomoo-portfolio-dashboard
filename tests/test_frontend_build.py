from pathlib import Path
import shutil
from uuid import uuid4

from scripts.build_frontend import build_frontend


def test_build_frontend_writes_static_pages_config():
    output_dir = Path(".tmp_testdata") / f"frontend-{uuid4().hex}"

    try:
        build_frontend(
            output_dir,
            api_base_url="https://api.example.com/",
            read_only=True,
            requires_write_token=True,
        )

        index_html = (output_dir / "index.html").read_text(encoding="utf-8")
        config_js = (output_dir / "config.js").read_text(encoding="utf-8")

        assert 'href="styles.css?v=' in index_html
        assert 'src="config.js?v=' in index_html
        assert 'src="dashboard.js?v=' in index_html
        assert "/static/dashboard.js" not in index_html
        assert '"apiBaseUrl": "https://api.example.com"' in config_js
        assert '"readOnly": true' in config_js
        assert '"requiresWriteToken": true' in config_js
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
