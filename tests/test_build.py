import os
from unittest.mock import patch

import build


def test_find_all_python_files(tmp_path):
    # Test-Ordnerstruktur anlegen
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("# python code")
    (src / "helper.py").write_text("# python code")
    (src / "notes.txt").write_text("not python")

    # Ausgeschlossenes Verzeichnis
    excluded = src / "venv"
    excluded.mkdir()
    (excluded / "ignored.py").write_text("# ignored code")

    found_files = build.find_all_python_files(str(src))
    filenames = [os.path.basename(f) for f in found_files]

    assert "app.py" in filenames
    assert "helper.py" in filenames
    assert "ignored.py" not in filenames
    assert "notes.txt" not in filenames


def test_create_cython_extensions():
    files = [os.path.join(".", "main.py"), os.path.join(".", "utils", "helper.py")]
    exts = build.create_cython_extensions(files)

    assert len(exts) == 2
    assert exts[0].name in ["main", ".main"]
    assert "helper" in exts[1].name


def test_create_pyinstaller_command():
    cmd = build.create_pyinstaller_command("main.py", "test_app")

    assert "pyinstaller" in cmd
    assert "--onedir" in cmd
    assert "--name" in cmd
    assert "test_app" in cmd
    assert "--windowed" in cmd
    assert "--hidden-import" in cmd
    assert "wmi" in cmd


@patch("platform.system", return_value="Windows")
@patch("subprocess.run")
def test_kill_process_if_running_windows(mock_run, mock_system):
    build.kill_process_if_running("test_app")
    mock_run.assert_called_once()
    args, _kwargs = mock_run.call_args
    assert args[0] == ["taskkill", "/F", "/IM", "test_app.exe"]


@patch("platform.system", return_value="Linux")
@patch("subprocess.run")
def test_kill_process_if_running_linux(mock_run, mock_system):
    build.kill_process_if_running("test_app")
    mock_run.assert_called_once()
    args, _kwargs = mock_run.call_args
    assert args[0] == ["pkill", "-f", "test_app"]


def test_cleanup_build_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "build_temp_12345").mkdir()
    (tmp_path / "dist_12345").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "keep_dir").mkdir()

    build.cleanup_build_files()

    assert not (tmp_path / "build_temp_12345").exists()
    assert not (tmp_path / "dist_12345").exists()
    assert not (tmp_path / "build").exists()
    assert (tmp_path / "keep_dir").exists()


def test_final_cleanup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    build_temp = tmp_path / build.BUILD_TEMP
    build_temp.mkdir()
    spec_file = tmp_path / f"{build.APP_NAME}.spec"
    spec_file.write_text("spec content")

    # Erstelle eine temporäre .c Datei
    c_file = tmp_path / "test_module.c"
    c_file.write_text("// C code")

    build.final_cleanup()

    assert not build_temp.exists()
    assert not spec_file.exists()
    assert not c_file.exists()
