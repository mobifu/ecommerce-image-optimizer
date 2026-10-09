import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import build
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


def test_decompression_bomb_caught_in_batch(tmp_path):
    """Testet, dass DecompressionBombError im Verarbeitungs-Batch abgefangen wird."""
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()

    bomb_file = src_dir / "bomb.jpg"
    Image.new("RGB", (10, 10), color="black").save(bomb_file)

    def mock_bomb_process(filename, in_f, out_f):
        raise Image.DecompressionBombError("DecompressionBombError test triggered")

    app = MagicMock(spec=main.App)
    app.progress_bar = MagicMock()
    app.after = lambda ms, func: func() if callable(func) else None

    # Darf keine unbehandelte Exception werfen
    main.App._run_image_processing(
        app,
        task_name="Bomb Test",
        input_folder=str(src_dir),
        output_folder=str(dest_dir),
        file_types=(".jpg",),
        process_function=mock_bomb_process,
        show_completion_message=False,
    )


def test_validate_dimensions():
    """Testet die Validierung von Bildabmessungen gegen ungültige Werte."""
    # Gültige Werte
    assert main.validate_dimensions("800", "600") == (800, 600)
    assert main.validate_dimensions(1920, 1080) == (1920, 1080)

    # Ungültige Werte (Bereichsüberschreitung oder Typfehler)
    with pytest.raises(ValueError):
        main.validate_dimensions("0", "100")

    with pytest.raises(ValueError):
        main.validate_dimensions("-50", "100")

    with pytest.raises(ValueError):
        main.validate_dimensions("20000", "100")

    with pytest.raises(ValueError):
        main.validate_dimensions("abc", "100")


def test_open_url_validation():
    """Stellt sicher, dass nur HTTP/HTTPS-URLs im Browser geöffnet werden."""
    app = MagicMock(spec=main.App)

    with patch("webbrowser.open_new") as mock_open:
        main.App.open_url(app, "https://www.agentur-schoelzke.de")
        mock_open.assert_called_once_with("https://www.agentur-schoelzke.de")

    with patch("webbrowser.open_new") as mock_open:
        main.App.open_url(app, "file:///C:/Windows/System32/cmd.exe")
        mock_open.assert_not_called()

    with patch("webbrowser.open_new") as mock_open:
        main.App.open_url(app, "javascript:alert(1)")
        mock_open.assert_not_called()


def test_backup_security_exclusions(tmp_path):
    """Testet, dass sichern.py sensible Dateien und Secrets strikt ausschließt (sofern lokal vorhanden)."""
    sichern = pytest.importorskip("sichern", reason="sichern.py ist ein lokales Wartungsskript")
    assert sichern.is_sensitive_or_excluded_file(".env")
    assert sichern.is_sensitive_or_excluded_file(".env.local")
    assert sichern.is_sensitive_or_excluded_file("settings.json")
    assert sichern.is_sensitive_or_excluded_file("settings.json.tmp")
    assert sichern.is_sensitive_or_excluded_file("secret.key")
    assert sichern.is_sensitive_or_excluded_file("server.pem")
    assert not sichern.is_sensitive_or_excluded_file("main.py")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (src_dir / ".env").write_text("SECRET=123", encoding="utf-8")
    (src_dir / "settings.json").write_text("{}", encoding="utf-8")

    backup_dest = tmp_path / "backups"
    zip_path = sichern.create_backup(source_dir=src_dir, backup_base_dir=backup_dest)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "main.py" in namelist
        assert ".env" not in namelist
        assert "settings.json" not in namelist


def test_kill_process_rejects_malicious_names():
    """Testet, dass ungültige Prozessnamen abgewiesen werden."""
    with patch("subprocess.run") as mock_run:
        build.kill_process_if_running("app; rm -rf /")
        mock_run.assert_not_called()

    with patch("subprocess.run") as mock_run:
        build.kill_process_if_running("valid_app_name-123")
        mock_run.assert_called_once()
