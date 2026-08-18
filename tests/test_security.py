import json
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

import main


def test_gitignore_ignores_sensitive_files():
    """Stellt sicher, dass sensible Dateien in .gitignore gelistet sind."""
    gitignore_path = Path(".gitignore").resolve()
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert "settings.json" in content
    assert ".env" in content
    assert "*.key" in content or "*.pem" in content


def test_decompression_bomb_protection_limit():
    """Stellt sicher, dass Pillow MAX_IMAGE_PIXELS konfiguriert ist."""
    assert Image.MAX_IMAGE_PIXELS is not None
    assert Image.MAX_IMAGE_PIXELS == 120_000_000


def test_settings_save_and_load_with_env(tmp_path, monkeypatch):
    """Testet das Laden von Einstellungen mit Umgebungsvariablen-Vorrang."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TINYPNG_API_KEY", "env_secret_key_999")
    monkeypatch.setenv("COMP_SOURCE_DIR", "env_source_dir")

    app = MagicMock(spec=main.App)
    app.comp_source_entry = MagicMock()
    app.comp_dest_entry = MagicMock()
    app.webp_source_entry = MagicMock()
    app.webp_dest_entry = MagicMock()
    app.tinypng_source_entry = MagicMock()
    app.tinypng_dest_entry = MagicMock()
    app.tinypng_api_key_entry = MagicMock()

    main.App.load_settings(app)

    app.tinypng_api_key_entry.insert.assert_called_with(0, "env_secret_key_999")
    app.comp_source_entry.insert.assert_called_with(0, "env_source_dir")


def test_settings_safe_path_resolution(tmp_path, monkeypatch):
    """Testet, dass Settings sicher geladen und gespeichert werden können."""
    monkeypatch.chdir(tmp_path)

    app = MagicMock(spec=main.App)
    app.comp_source_entry = MagicMock(get=lambda: "C:/safe/input")
    app.comp_dest_entry = MagicMock(get=lambda: "C:/safe/output")
    app.webp_source_entry = MagicMock(get=lambda: "C:/safe/webp_in")
    app.webp_dest_entry = MagicMock(get=lambda: "C:/safe/webp_out")
    app.tinypng_source_entry = MagicMock(get=lambda: "C:/safe/tiny_in")
    app.tinypng_dest_entry = MagicMock(get=lambda: "C:/safe/tiny_out")
    app.tinypng_api_key_entry = MagicMock(get=lambda: "valid_secret_key_123")

    main.App.save_settings(app)

    saved_file = (tmp_path / "settings.json").resolve()
    assert saved_file.exists()

    with open(saved_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["tinypng_api_key"] == "valid_secret_key_123"


def test_invalid_settings_json_graceful_handling(tmp_path, monkeypatch):
    """Stellt sicher, dass eine korrumpierte settings.json keinen Crash verursacht."""
    monkeypatch.chdir(tmp_path)
    corrupted_file = tmp_path / "settings.json"
    corrupted_file.write_text("{ invalid_json: true ", encoding="utf-8")

    app = MagicMock(spec=main.App)
    main.App.load_settings(app)
