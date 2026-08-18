import json
from unittest.mock import MagicMock, patch

from PIL import Image

import main


def test_textbox_logger():
    mock_textbox = MagicMock()
    logger = main.TextboxLogger(mock_textbox)

    logger.write("Hello World")
    mock_textbox.configure.assert_any_call(state="normal")
    mock_textbox.insert.assert_called_with("end", "Hello World")
    mock_textbox.see.assert_called_with("end")
    mock_textbox.configure.assert_any_call(state="disabled")

    # flush test
    logger.flush()


def test_settings_save_and_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Mock App Instanz erstellen
    app = MagicMock(spec=main.App)
    app.comp_source_entry = MagicMock(get=lambda: "src_comp")
    app.comp_dest_entry = MagicMock(get=lambda: "dest_comp")
    app.webp_source_entry = MagicMock(get=lambda: "src_webp")
    app.webp_dest_entry = MagicMock(get=lambda: "dest_webp")
    app.tinypng_source_entry = MagicMock(get=lambda: "src_tiny")
    app.tinypng_dest_entry = MagicMock(get=lambda: "dest_tiny")
    app.tinypng_api_key_entry = MagicMock(get=lambda: "key123")

    # Speichern testen
    main.App.save_settings(app)

    assert (tmp_path / "settings.json").exists()

    with open(tmp_path / "settings.json") as f:
        data = json.load(f)

    assert data["comp_source"] == "src_comp"
    assert data["tinypng_api_key"] == "key123"


def test_update_image_count_and_processing(tmp_path):
    # Testbilder erstellen
    img1 = tmp_path / "test1.jpg"
    img2 = tmp_path / "test2.png"
    txt = tmp_path / "test.txt"

    Image.new("RGB", (100, 100), color="red").save(img1)
    Image.new("RGB", (100, 100), color="blue").save(img2)
    txt.write_text("hello")

    mock_info_label = MagicMock()
    app = MagicMock(spec=main.App)

    main.App.update_image_count(app, str(tmp_path), mock_info_label, (".jpg", ".jpeg", ".png"))
    mock_info_label.configure.assert_called_with(text="2 Bild(er) gefunden", text_color="gray60")


def test_update_quality_and_png_sliders():
    app = MagicMock(spec=main.App)
    app.comp_quality_entry = MagicMock()
    app.comp_quality_slider = MagicMock()
    app.comp_png_level_entry = MagicMock()
    app.comp_png_level_slider = MagicMock()

    # Slider update test
    main.App.update_quality_from_slider(app, 80.0)
    app.comp_quality_entry.delete.assert_called_with(0, "end")
    app.comp_quality_entry.insert.assert_called_with(0, "80")

    # Entry update test
    app.comp_quality_entry.get.return_value = "90"
    main.App.update_quality_from_entry(app, None)
    app.comp_quality_slider.set.assert_called_with(90)


def test_run_image_processing_basic(tmp_path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()

    img_file = src_dir / "sample.jpg"
    Image.new("RGB", (50, 50), color="white").save(img_file)

    processed_files = []

    def mock_process(filename, input_folder, output_folder):
        processed_files.append(filename)

    app = MagicMock(spec=main.App)
    app.progress_bar = MagicMock()

    main.App._run_image_processing(
        app,
        task_name="Test Task",
        input_folder=str(src_dir),
        output_folder=str(dest_dir),
        file_types=(".jpg",),
        process_function=mock_process,
        show_completion_message=False,
    )

    assert "sample.jpg" in processed_files
    assert dest_dir.exists()


@patch("main.messagebox.showinfo")
def test_run_compression(mock_showinfo, tmp_path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()

    jpg_file = src_dir / "test.jpg"
    png_file = src_dir / "test.png"
    Image.new("RGB", (200, 200), color="red").save(jpg_file)
    Image.new("RGBA", (200, 200), color="blue").save(png_file)

    app = MagicMock()
    app._run_image_processing = (
        lambda task_name,
        in_folder,
        out_folder,
        exts,
        proc,
        show_completion_message=True: main.App._run_image_processing(
            app, task_name, in_folder, out_folder, exts, proc, show_completion_message
        )
    )
    app.after = lambda ms, func: func() if callable(func) else None

    main.App.run_compression(
        app,
        input_folder=str(src_dir),
        output_folder=str(dest_dir),
        quality=80,
        png_level=6,
        should_resize=True,
        max_size=(100, 100),
    )

    assert (dest_dir / "test.jpg").exists()
    assert (dest_dir / "test.png").exists()

    with Image.open(dest_dir / "test.jpg") as img:
        assert img.size[0] <= 100
        assert img.size[1] <= 100


@patch("main.messagebox.showinfo")
def test_run_webp_conversion(mock_showinfo, tmp_path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()

    jpg_file = src_dir / "photo.jpg"
    Image.new("RGB", (300, 300), color="green").save(jpg_file)

    app = MagicMock()
    app._run_image_processing = (
        lambda task_name,
        in_folder,
        out_folder,
        exts,
        proc,
        show_completion_message=True: main.App._run_image_processing(
            app, task_name, in_folder, out_folder, exts, proc, show_completion_message
        )
    )
    app.after = lambda ms, func: func() if callable(func) else None

    main.App.run_webp_conversion(
        app,
        input_folder=str(src_dir),
        output_folder=str(dest_dir),
        quality=75,
        should_resize=True,
        max_size=(150, 150),
    )


@patch("main.tinify")
@patch("main.messagebox.showinfo")
def test_run_tinypng_compression_success(mock_showinfo, mock_tinify, tmp_path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()

    jpg_file = src_dir / "sample.jpg"
    Image.new("RGB", (200, 200), color="yellow").save(jpg_file)

    mock_source = MagicMock()
    mock_tinify.from_buffer.return_value = mock_source
    mock_tinify.validate.return_value = True

    app = MagicMock()
    app._run_image_processing = (
        lambda task_name,
        in_folder,
        out_folder,
        exts,
        proc,
        show_completion_message=True: main.App._run_image_processing(
            app, task_name, in_folder, out_folder, exts, proc, show_completion_message
        )
    )
    app.after = lambda ms, func: func() if callable(func) else None

    main.App.run_tinypng_compression(
        app,
        api_key="valid_key",
        input_folder=str(src_dir),
        output_folder=str(dest_dir),
        should_resize=False,
        max_size=(100, 100),
    )

    mock_tinify.validate.assert_called_once()
    mock_tinify.from_buffer.assert_called_once()
    mock_source.to_file.assert_called_once()


@patch("main.tinify")
@patch("main.messagebox.showerror")
def test_run_tinypng_compression_invalid_key(mock_showerror, mock_tinify, tmp_path):
    mock_tinify.Error = Exception
    mock_tinify.validate.side_effect = mock_tinify.Error("Invalid key")

    app = MagicMock()
    app.after = lambda ms, func: func() if callable(func) else None

    main.App.run_tinypng_compression(
        app,
        api_key="invalid_key",
        input_folder=str(tmp_path),
        output_folder=str(tmp_path),
        should_resize=False,
        max_size=(100, 100),
    )

    mock_showerror.assert_called_once()
