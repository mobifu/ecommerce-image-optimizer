import contextlib
import io
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from collections.abc import Callable
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tinify
from PIL import Image, ImageOps

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Decompression Bomb Schutz (120 Megapixel Limit)
Image.MAX_IMAGE_PIXELS = 120_000_000

# Konstanten für Pfade und Einstellungen
DEFAULT_INPUT_FOLDER = "Bilder_original"
DEFAULT_OUTPUT_FOLDER = "Bilder_komprimiert"

# --- Footer-Informationen ---
COMPANY_NAME = f"© Agentur Schölzke {date.today().year}"
COMPANY_URL = "https://www.agentur-schoelzke.de"
DONATE_URL = "https://paypal.me/kaischoelzke"
VERSION_INFO = "v1.12.1"

SUPPORTED_EXTENSIONS_COMPRESSION = (".jpg", ".jpeg", ".png")
SUPPORTED_EXTENSIONS_CONVERSION = (".png", ".jpg", ".jpeg")
SUPPORTED_EXTENSIONS_TINYPNG = (".png", ".jpg", ".jpeg")


# ============================================================================
# Kernlogik & Validierung (GUI-unabhängig)
# ============================================================================


def validate_dimensions(
    width_val: int | str,
    height_val: int | str,
    min_dim: int = 1,
    max_dim: int = 16384,
) -> tuple[int, int]:
    """Validiert Breiten- und Höhenangaben gegen ungültige Werte und Memory-Exhaustion."""
    try:
        width = int(width_val)
        height = int(height_val)
    except (ValueError, TypeError) as err:
        raise ValueError("Bitte geben Sie für Breite und Höhe ganze Zahlen ein.") from err

    if not (min_dim <= width <= max_dim and min_dim <= height <= max_dim):
        raise ValueError(f"Abmessungen müssen zwischen {min_dim} und {max_dim} Pixeln liegen.")
    return width, height


def sync_slider_to_entry(entry_widget: ctk.CTkEntry, value: float | int) -> None:
    """Aktualisiert das Eingabefeld synchron zum Slider-Wert."""
    entry_widget.delete(0, "end")
    entry_widget.insert(0, str(int(value)))


def sync_entry_to_slider(
    entry_widget: ctk.CTkEntry,
    slider_widget: ctk.CTkSlider,
    min_val: int,
    max_val: int,
) -> None:
    """Validiert die Texteingabe und aktualisiert den Slider synchron im definierten Wertebereich."""
    try:
        raw_val = int(entry_widget.get())
        clamped_val = max(min_val, min(max_val, raw_val))
        if raw_val != clamped_val:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, str(clamped_val))
        slider_widget.set(clamped_val)
    except (ValueError, TypeError):
        pass


def save_settings_file(settings: dict[str, str], filepath: Path | str = "settings.json") -> None:
    """Speichert Konfigurationseinstellungen atomar und permissions-gesichert als JSON."""
    settings_path = Path(filepath).resolve()
    temp_path = settings_path.with_suffix(".json.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)
        f.flush()
        os.fsync(f.fileno())

    # Auf POSIX-Systemen restriktive Zugriffsrechte vergeben
    if hasattr(os, "chmod") and os.name != "nt":
        with contextlib.suppress(OSError):
            os.chmod(temp_path, 0o600)

    temp_path.replace(settings_path)


def load_settings_file(filepath: Path | str = "settings.json") -> dict[str, str]:
    """Lädt gespeicherte Einstellungen sicher aus einer JSON-Datei."""
    settings_path = Path(filepath).resolve()
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            print(f"Fehler beim Laden der Einstellungen aus {settings_path}: {e}")
    return {}


def get_merged_settings(filepath: Path | str = "settings.json") -> dict[str, str]:
    """Kombiniert Umgebungsvariablen mit Einstellungen aus der Datei und Standardwerten."""
    stored = load_settings_file(filepath)
    return {
        "comp_source": os.getenv("COMP_SOURCE_DIR")
        or stored.get("comp_source", DEFAULT_INPUT_FOLDER),
        "comp_dest": os.getenv("COMP_DEST_DIR") or stored.get("comp_dest", DEFAULT_OUTPUT_FOLDER),
        "webp_source": os.getenv("WEBP_SOURCE_DIR")
        or stored.get("webp_source", DEFAULT_INPUT_FOLDER),
        "webp_dest": os.getenv("WEBP_DEST_DIR") or stored.get("webp_dest", "Bilder_webp"),
        "tinypng_source": os.getenv("TINYPNG_SOURCE_DIR")
        or stored.get("tinypng_source", DEFAULT_INPUT_FOLDER),
        "tinypng_dest": os.getenv("TINYPNG_DEST_DIR")
        or stored.get("tinypng_dest", DEFAULT_OUTPUT_FOLDER),
        "tinypng_api_key": (
            os.getenv("TINYPNG_API_KEY") or stored.get("tinypng_api_key", "")
        ).strip(),
    }


def compress_image_file(
    source_path: Path,
    dest_path: Path,
    quality: int,
    png_level: int,
    should_resize: bool,
    max_size: tuple[int, int],
) -> None:
    """Komprimiert eine einzelne Bilddatei (JPG oder PNG) lokal via Pillow."""
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        if should_resize:
            img.thumbnail(max_size)

        ext = source_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            img.save(dest_path, "JPEG", quality=quality, optimize=True)
            print(f"Komprimiert (JPG): {source_path.name}")
        elif ext == ".png":
            img.save(dest_path, "PNG", optimize=True, compress_level=png_level)
            print(f"Komprimiert (PNG): {source_path.name}")


def convert_image_to_webp(
    source_path: Path,
    dest_path: Path,
    quality: int,
    should_resize: bool,
    max_size: tuple[int, int],
) -> None:
    """Konvertiert eine Bilddatei in das WebP-Format."""
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        if should_resize:
            img.thumbnail(max_size)
        img.save(dest_path, "WEBP", quality=quality)
        print(f"Konvertiert: {source_path.name} -> {dest_path.name}")


def compress_image_tinypng(
    source_path: Path,
    dest_path: Path,
    should_resize: bool,
    max_size: tuple[int, int],
) -> None:
    """Sendet ein Bild über die TinyPNG API zur Cloud-Komprimierung."""
    print(f"Komprimiere: {source_path.name} ...")
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        img_format = img.format or (
            "JPEG" if source_path.suffix.lower() in (".jpg", ".jpeg") else "PNG"
        )
        buffer = io.BytesIO()
        img.save(buffer, format=img_format)
        buffer.seek(0)
        source = tinify.from_buffer(buffer.read())

    if should_resize:
        resized = source.resize(method="fit", width=max_size[0], height=max_size[1])
        resized.to_file(str(dest_path))
    else:
        source.to_file(str(dest_path))
    print(f"Fertig: {source_path.name} gespeichert in {dest_path.parent}")


# ============================================================================
# GUI-Hilfsklassen
# ============================================================================


class TextboxLogger:
    """Leitet print-Ausgaben in ein CTkTextbox-Widget um."""

    def __init__(self, textbox: ctk.CTkTextbox) -> None:
        self.textbox = textbox

    def write(self, text: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def flush(self) -> None:
        pass


# ============================================================================
# Hauptanwendungs-GUI
# ============================================================================


class App(ctk.CTk):
    """Hauptfenster der Bildbearbeitungs-Anwendung."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Bildbearbeitungstool")
        self.geometry("900x950")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Footer unten verankern
        self.create_footer()

        # Tabs initialisieren
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tabview.add("Komprimieren")
        self.tabview.add("WebP Konvertieren")
        self.tabview.add("TinyPNG")

        self.create_compression_tab()
        self.create_conversion_tab()
        self.create_tinypng_tab()

        # Fortschrittsanzeige
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=(10, 0), fill="x")

        # Unterer Bereich für Vorschau und Logs
        self.bottom_tabview = ctk.CTkTabview(self)
        self.bottom_tabview.pack(padx=20, pady=(10, 20), fill="x")

        self.bottom_tabview.add("Vorschau")
        self.bottom_tabview.add("Logs")

        self.thumbnail_frame = ctk.CTkScrollableFrame(
            self.bottom_tabview.tab("Vorschau"), label_text="Bildvorschau", height=150
        )
        self.thumbnail_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.thumbnail_frame.grid_columnconfigure(0, weight=1)

        self.log_textbox = ctk.CTkTextbox(
            self.bottom_tabview.tab("Logs"), height=200, state="disabled"
        )
        self.log_textbox.pack(padx=10, pady=(10, 0), fill="x")

        log_button_frame = ctk.CTkFrame(self.bottom_tabview.tab("Logs"), fg_color="transparent")
        log_button_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(log_button_frame, text="Logs leeren", command=self.clear_logs).pack(
            side="right"
        )

        logger = TextboxLogger(self.log_textbox)
        sys.stdout = logger
        sys.stderr = logger

        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def clear_logs(self) -> None:
        """Leert das Log-Textfeld."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        print("Logs gelöscht.")

    def create_footer(self) -> None:
        """Erstellt den Footer mit Versionsinfo und Firmenlink."""
        footer_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        footer_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 10))

        version_label = ctk.CTkLabel(footer_frame, text=VERSION_INFO, text_color="gray60")
        version_label.pack(side="left")

        company_label = ctk.CTkLabel(
            footer_frame, text=COMPANY_NAME, text_color="#1f6aa5", cursor="hand2"
        )
        company_label.pack(side="right")
        company_label.bind("<Button-1>", lambda _e: self.open_url(COMPANY_URL))

        donate_label = ctk.CTkLabel(
            footer_frame, text="☕ Spenden", text_color="#1f6aa5", cursor="hand2"
        )
        donate_label.pack(side="right", padx=(0, 15))
        donate_label.bind("<Button-1>", lambda _e: self.open_url(DONATE_URL))

    def open_url(self, url: str) -> None:
        """Öffnet eine validierte HTTP(S)-URL im Standard-Webbrowser."""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                webbrowser.open_new(url)
            else:
                print(f"Ungültige oder abgewiesene URL: {url}")
        except Exception as e:
            print(f"Fehler beim Öffnen der URL {url}: {e}")

    def select_folder(
        self,
        entry_widget: ctk.CTkEntry,
        info_label: ctk.CTkLabel | None = None,
        file_types: tuple[str, ...] | None = None,
    ) -> None:
        """Öffnet einen Dialog zur Ordnerauswahl und trägt den Pfad in das Entry-Widget ein."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, folder_path)
            if info_label and file_types:
                self.update_image_count(folder_path, info_label, file_types)
                self.update_thumbnails(folder_path, file_types)

    def update_image_count(
        self, folder_path: str, info_label: ctk.CTkLabel, file_types: tuple[str, ...]
    ) -> None:
        """Zählt passende Bilddateien im Ordner und aktualisiert das Info-Label."""
        try:
            resolved_dir = Path(folder_path).resolve()
            if not resolved_dir.is_dir():
                info_label.configure(text="Ordner nicht gefunden", text_color="orange")
                return

            count = sum(1 for f in os.listdir(resolved_dir) if f.lower().endswith(file_types))
            info_label.configure(text=f"{count} Bild(er) gefunden", text_color="gray60")
        except Exception as e:
            info_label.configure(text="Fehler beim Lesen", text_color="red")
            print(f"Fehler beim Zählen der Bilder: {e}")
        self.update_idletasks()

    def update_thumbnails(self, folder_path: str, file_types: tuple[str, ...]) -> None:
        """Erstellt und zeigt Thumbnails für bis zu 50 Bilder im ausgewählten Ordner an."""
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()

        try:
            resolved_dir = Path(folder_path).resolve()
            if not resolved_dir.is_dir():
                return

            files = [f for f in os.listdir(resolved_dir) if f.lower().endswith(file_types)]
            for filename in files[:50]:
                img_path = (resolved_dir / filename).resolve()
                with Image.open(img_path) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((100, 100))
                    ctk_img = ctk.CTkImage(light_image=img, size=img.size)
                    label = ctk.CTkLabel(self.thumbnail_frame, image=ctk_img, text="")
                    label.image = ctk_img  # type: ignore[attr-defined]
                    label.pack(side="left", padx=5, pady=5)
        except Exception as e:
            print(f"Fehler beim Erstellen der Thumbnails: {e}")

    def save_settings(self) -> None:
        """Speichert die aktuellen Pfade und den API-Key atomar in settings.json."""
        settings = {
            "comp_source": self.comp_source_entry.get(),
            "comp_dest": self.comp_dest_entry.get(),
            "webp_source": self.webp_source_entry.get(),
            "webp_dest": self.webp_dest_entry.get(),
            "tinypng_source": self.tinypng_source_entry.get(),
            "tinypng_dest": self.tinypng_dest_entry.get(),
            "tinypng_api_key": self.tinypng_api_key_entry.get().strip(),
        }
        try:
            save_settings_file(settings)
            print("Einstellungen gespeichert.")
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")

    def load_settings(self) -> None:
        """Lädt Pfade und API-Key aus Umgebungsvariablen oder settings.json."""
        try:
            merged = get_merged_settings()

            for entry in (
                self.comp_source_entry,
                self.comp_dest_entry,
                self.webp_source_entry,
                self.webp_dest_entry,
                self.tinypng_source_entry,
                self.tinypng_dest_entry,
                self.tinypng_api_key_entry,
            ):
                entry.delete(0, "end")

            self.comp_source_entry.insert(0, merged["comp_source"])
            self.comp_dest_entry.insert(0, merged["comp_dest"])
            self.webp_source_entry.insert(0, merged["webp_source"])
            self.webp_dest_entry.insert(0, merged["webp_dest"])
            self.tinypng_source_entry.insert(0, merged["tinypng_source"])
            self.tinypng_dest_entry.insert(0, merged["tinypng_dest"])
            self.tinypng_api_key_entry.insert(0, merged["tinypng_api_key"])

            self.after(100, self.update_ui_for_current_tab)
            print("Einstellungen geladen.")
        except Exception as e:
            print(f"Fehler beim Laden der Einstellungen: {e}")

    def update_ui_for_current_tab(self) -> None:
        """Aktualisiert die Bildanzahl und Thumbnails für den aktuell ausgewählten Tab."""
        tab_mappings: dict[str, tuple[ctk.CTkEntry, ctk.CTkLabel, tuple[str, ...]]] = {
            "Komprimieren": (
                self.comp_source_entry,
                self.comp_source_info_label,
                SUPPORTED_EXTENSIONS_COMPRESSION,
            ),
            "WebP Konvertieren": (
                self.webp_source_entry,
                self.webp_source_info_label,
                SUPPORTED_EXTENSIONS_CONVERSION,
            ),
            "TinyPNG": (
                self.tinypng_source_entry,
                self.tinypng_source_info_label,
                SUPPORTED_EXTENSIONS_TINYPNG,
            ),
        }
        current_tab_name = self.tabview.get()
        if mapping := tab_mappings.get(current_tab_name):
            entry_widget, info_label, extensions = mapping
            folder = entry_widget.get()
            self.update_image_count(folder, info_label, extensions)
            self.update_thumbnails(folder, extensions)

    def on_closing(self) -> None:
        """Wird aufgerufen, wenn das Fenster geschlossen wird."""
        self.save_settings()
        self.destroy()

    def _create_folder_selection_block(
        self,
        parent_tab: ctk.CTkFrame,
        label_text: str,
        entry_attr_name: str,
        info_label_attr_name: str | None = None,
        file_types: tuple[str, ...] | None = None,
        is_source: bool = True,
    ) -> None:
        """Erstellt einen UI-Block für die Auswahl eines Quell- oder Zielordners."""
        frame = ctk.CTkFrame(parent_tab)
        frame.pack(padx=20, pady=(10, 5) if is_source else (0, 5), fill="x")
        ctk.CTkLabel(frame, text=label_text).pack(
            anchor="w", padx=10, pady=(5, 0) if is_source else (10, 0)
        )

        input_controls_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_controls_frame.pack(fill="x", padx=10, pady=(0, 5))

        entry_widget = ctk.CTkEntry(input_controls_frame)
        entry_widget.pack(side="left", fill="x", expand=True)
        setattr(self, entry_attr_name, entry_widget)

        if is_source:
            info_label = ctk.CTkLabel(frame, text="")
            info_label.pack(anchor="w", padx=10, pady=(0, 5))
            if info_label_attr_name:
                setattr(self, info_label_attr_name, info_label)

            def browse_command() -> None:
                self.select_folder(entry_widget, info_label, file_types)
        else:

            def browse_command() -> None:
                self.select_folder(entry_widget)

        browse_button = ctk.CTkButton(
            input_controls_frame, text="Durchsuchen...", command=browse_command
        )
        browse_button.pack(side="right", padx=(5, 0))

    def _create_resize_options_block(
        self,
        parent_tab: ctk.CTkFrame,
        check_attr_name: str,
        width_attr_name: str,
        height_attr_name: str,
    ) -> None:
        """Erstellt einen UI-Block für die optionalen Bildgrößenanpassungen."""
        resize_frame = ctk.CTkFrame(parent_tab)
        resize_frame.pack(padx=20, pady=10, fill="x")

        resize_check = ctk.CTkCheckBox(resize_frame, text="Bildgröße anpassen (proportional)")
        resize_check.pack(anchor="w", padx=10, pady=10)
        setattr(self, check_attr_name, resize_check)

        size_inner_frame = ctk.CTkFrame(resize_frame, fg_color="transparent")
        size_inner_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(size_inner_frame, text="Max. Breite:").pack(side="left")
        width_entry = ctk.CTkEntry(size_inner_frame, width=80)
        width_entry.pack(side="left", padx=(5, 20))
        width_entry.insert(0, "1024")
        setattr(self, width_attr_name, width_entry)

        ctk.CTkLabel(size_inner_frame, text="Max. Höhe:").pack(side="left")
        height_entry = ctk.CTkEntry(size_inner_frame, width=80)
        height_entry.pack(side="left", padx=5)
        height_entry.insert(0, "1024")
        setattr(self, height_attr_name, height_entry)

    def create_slider_row(
        self,
        parent: ctk.CTkFrame,
        row_idx: int,
        label_text: str,
        min_val: int,
        max_val: int,
        default_val: int,
        unit_text: str,
        slider_attr_name: str,
        entry_attr_name: str,
        steps: int | None = None,
    ) -> None:
        """Erstellt eine standardisierte Zeile aus Label, Schieberegler und synchronem Eingabefeld."""
        ctk.CTkLabel(parent, text=label_text).grid(row=row_idx, column=0, padx=(10, 5), pady=10)

        entry = ctk.CTkEntry(parent, width=50)
        entry.insert(0, str(default_val))

        kwargs = {"from_": min_val, "to": max_val}
        if steps is not None:
            kwargs["number_of_steps"] = steps

        slider = ctk.CTkSlider(
            parent,
            command=lambda val: sync_slider_to_entry(entry, val),
            **kwargs,
        )
        slider.set(default_val)
        slider.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=10)

        entry.grid(row=row_idx, column=2, padx=5, pady=10)
        entry.bind(
            "<Return>",
            lambda _e: sync_entry_to_slider(entry, slider, min_val, max_val),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e: sync_entry_to_slider(entry, slider, min_val, max_val),
        )

        ctk.CTkLabel(parent, text=unit_text).grid(row=row_idx, column=3, padx=(0, 10), pady=10)

        setattr(self, slider_attr_name, slider)
        setattr(self, entry_attr_name, entry)

    def create_compression_tab(self) -> None:
        """Erstellt den Tab für die lokale Komprimierungsfunktion."""
        tab = self.tabview.tab("Komprimieren")

        self._create_folder_selection_block(
            tab,
            "Quellordner (JPG, JPEG, PNG)",
            "comp_source_entry",
            "comp_source_info_label",
            SUPPORTED_EXTENSIONS_COMPRESSION,
            is_source=True,
        )
        self._create_folder_selection_block(tab, "Zielordner:", "comp_dest_entry", is_source=False)

        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=10, fill="x")
        settings_frame.grid_columnconfigure(1, weight=1)

        self.create_slider_row(
            settings_frame,
            row_idx=0,
            label_text="Qualität (nur JPG):",
            min_val=0,
            max_val=100,
            default_val=75,
            unit_text="%",
            slider_attr_name="comp_quality_slider",
            entry_attr_name="comp_quality_entry",
        )
        self.create_slider_row(
            settings_frame,
            row_idx=1,
            label_text="Kompression (nur PNG):",
            min_val=0,
            max_val=9,
            default_val=6,
            unit_text="(0-9)",
            slider_attr_name="comp_png_level_slider",
            entry_attr_name="comp_png_level_entry",
            steps=9,
        )

        self._create_resize_options_block(
            tab, "comp_resize_check", "comp_width_entry", "comp_height_entry"
        )

        def start_thread() -> None:
            try:
                png_level = max(0, min(9, int(self.comp_png_level_entry.get())))
                quality = max(0, min(100, int(self.comp_quality_entry.get())))
                max_size = validate_dimensions(
                    self.comp_width_entry.get(),
                    self.comp_height_entry.get(),
                )
                threading.Thread(
                    target=self.run_compression,
                    args=(
                        self.comp_source_entry.get(),
                        self.comp_dest_entry.get(),
                        quality,
                        png_level,
                        self.comp_resize_check.get(),
                        max_size,
                    ),
                    daemon=True,
                ).start()
            except ValueError as err:
                messagebox.showerror("Ungültige Eingabe", str(err))

        ctk.CTkButton(tab, text="Komprimierung starten", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    # Abwärtskompatible Slider-Methoden
    def update_quality_from_slider(self, value: float | int) -> None:
        sync_slider_to_entry(self.comp_quality_entry, value)

    def update_quality_from_entry(self, _event: object = None) -> None:
        sync_entry_to_slider(self.comp_quality_entry, self.comp_quality_slider, 0, 100)

    def update_png_level_from_slider(self, value: float | int) -> None:
        sync_slider_to_entry(self.comp_png_level_entry, value)

    def update_png_level_from_entry(self, _event: object = None) -> None:
        sync_entry_to_slider(self.comp_png_level_entry, self.comp_png_level_slider, 0, 9)

    def _run_image_processing(
        self,
        task_name: str,
        input_folder: str,
        output_folder: str,
        file_types: tuple[str, ...],
        process_function: Callable[[str, str, str], None],
        show_completion_message: bool = True,
    ) -> None:
        """Generische Methode zur Stapelverarbeitung von Bilddateien in einem Ordner."""
        print(f"Starte Aufgabe: {task_name} für Ordner '{input_folder}'")

        in_resolved = Path(input_folder).resolve()
        out_resolved = Path(output_folder).resolve()

        if in_resolved == out_resolved and not messagebox.askyesno(
            "Warnung",
            "Quell- und Zielordner sind identisch. Das wird Ihre Originaldateien überschreiben!\n\nMöchten Sie wirklich fortfahren?",
        ):
            print("Vorgang vom Benutzer abgebrochen.")
            return

        try:
            if not in_resolved.is_dir():
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Fehler",
                        f"Der Quellordner wurde nicht gefunden:\n{in_resolved}",
                    ),
                )
                return

            out_resolved.mkdir(parents=True, exist_ok=True)

            files = [f for f in os.listdir(in_resolved) if f.lower().endswith(file_types)]
            if not files:
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Information",
                        f"Im Quellordner wurden keine passenden Bilder ({', '.join(file_types)}) gefunden.",
                    ),
                )
                return

            self.progress_bar.set(0)
            total_files = len(files)

            for i, filename in enumerate(files):
                try:
                    process_function(filename, str(in_resolved), str(out_resolved))
                except Exception as e:
                    print(f"Fehler bei der Verarbeitung von {filename}: {e}")
                    if "tinify.Error" in str(type(e)):
                        self.after(0, lambda: self.progress_bar.set(0))
                        return

                self.progress_bar.set((i + 1) / total_files)

            print(f"Aufgabe '{task_name}' abgeschlossen.")
            if show_completion_message:
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Fertig", f"Die Aufgabe '{task_name}' ist abgeschlossen."
                    ),
                )

        except Exception as e:
            self.after(
                0,
                lambda err=e: messagebox.showerror(
                    "Unerwarteter Fehler", f"Ein Fehler ist aufgetreten:\n{err}"
                ),
            )
        finally:
            self.after(100, lambda: self.progress_bar.set(0))

    def run_compression(
        self,
        input_folder: str,
        output_folder: str,
        quality: int,
        png_level: int,
        should_resize: bool,
        max_size: tuple[int, int],
    ) -> None:
        """Startet den lokalen Komprimierungsprozess für JPG und PNG."""
        if should_resize:
            print(f"Größenanpassung aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel.")

        def process(filename: str, in_folder: str, out_folder: str) -> None:
            safe_name = Path(filename).name
            source = (Path(in_folder).resolve() / safe_name).resolve()
            dest = (Path(out_folder).resolve() / safe_name).resolve()
            compress_image_file(source, dest, quality, png_level, should_resize, max_size)

        self._run_image_processing(
            "Lokale Komprimierung",
            input_folder,
            output_folder,
            SUPPORTED_EXTENSIONS_COMPRESSION,
            process,
        )

    def create_conversion_tab(self) -> None:
        """Erstellt den Tab für die Konvertierungsfunktionen."""
        tab = self.tabview.tab("WebP Konvertieren")

        self._create_folder_selection_block(
            tab,
            "Quellordner (PNG, JPG)",
            "webp_source_entry",
            "webp_source_info_label",
            SUPPORTED_EXTENSIONS_CONVERSION,
            is_source=True,
        )
        self._create_folder_selection_block(tab, "Zielordner:", "webp_dest_entry", is_source=False)

        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=10, fill="x")
        settings_frame.grid_columnconfigure(1, weight=1)

        self.create_slider_row(
            settings_frame,
            row_idx=0,
            label_text="Qualität (nur WebP):",
            min_val=0,
            max_val=100,
            default_val=80,
            unit_text="%",
            slider_attr_name="webp_quality_slider",
            entry_attr_name="webp_quality_entry",
        )

        self._create_resize_options_block(
            tab, "webp_resize_check", "webp_width_entry", "webp_height_entry"
        )

        def start_thread() -> None:
            try:
                quality = max(0, min(100, int(self.webp_quality_entry.get())))
                max_size = validate_dimensions(
                    self.webp_width_entry.get(),
                    self.webp_height_entry.get(),
                )
                threading.Thread(
                    target=self.run_webp_conversion,
                    args=(
                        self.webp_source_entry.get(),
                        self.webp_dest_entry.get(),
                        quality,
                        self.webp_resize_check.get(),
                        max_size,
                    ),
                    daemon=True,
                ).start()
            except ValueError as err:
                messagebox.showerror("Ungültige Eingabe", str(err))

        ctk.CTkButton(tab, text="Nach WebP konvertieren", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    def update_webp_quality_from_slider(self, value: float | int) -> None:
        sync_slider_to_entry(self.webp_quality_entry, value)

    def update_webp_quality_from_entry(self, _event: object = None) -> None:
        sync_entry_to_slider(self.webp_quality_entry, self.webp_quality_slider, 0, 100)

    def run_webp_conversion(
        self,
        input_folder: str,
        output_folder: str,
        quality: int,
        should_resize: bool,
        max_size: tuple[int, int],
    ) -> None:
        """Startet die Stapelkonvertierung in das WebP-Format."""
        if should_resize:
            print(f"Größenanpassung aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel.")

        def process(filename: str, in_folder: str, out_folder: str) -> None:
            safe_name = Path(filename).name
            source = (Path(in_folder).resolve() / safe_name).resolve()
            dest = (Path(out_folder).resolve() / f"{Path(safe_name).stem}.webp").resolve()
            convert_image_to_webp(source, dest, quality, should_resize, max_size)

        self._run_image_processing(
            "WebP Konvertierung",
            input_folder,
            output_folder,
            SUPPORTED_EXTENSIONS_CONVERSION,
            process,
        )

    def create_tinypng_tab(self) -> None:
        """Erstellt den Tab für die TinyPNG-Funktionen."""
        tab = self.tabview.tab("TinyPNG")

        ctk.CTkLabel(tab, text="TinyPNG API Key:").pack(padx=20, pady=(10, 0))
        self.tinypng_api_key_entry = ctk.CTkEntry(tab, width=400, show="*")
        self.tinypng_api_key_entry.pack(padx=20, pady=5)

        self._create_folder_selection_block(
            tab,
            "Quellordner (PNG, JPG)",
            "tinypng_source_entry",
            "tinypng_source_info_label",
            SUPPORTED_EXTENSIONS_TINYPNG,
            is_source=True,
        )
        self._create_folder_selection_block(
            tab, "Zielordner:", "tinypng_dest_entry", is_source=False
        )

        self._create_resize_options_block(
            tab, "tinypng_resize_check", "tinypng_width_entry", "tinypng_height_entry"
        )

        def start_thread() -> None:
            api_key = self.tinypng_api_key_entry.get().strip()
            if not api_key:
                messagebox.showerror("Fehler", "Bitte gib einen TinyPNG API-Key ein.")
                return
            try:
                max_size = validate_dimensions(
                    self.tinypng_width_entry.get(),
                    self.tinypng_height_entry.get(),
                )
                self.start_tinypng_thread(
                    api_key,
                    self.tinypng_source_entry.get(),
                    self.tinypng_dest_entry.get(),
                    self.tinypng_resize_check.get(),
                    max_size,
                )
            except ValueError as err:
                messagebox.showerror("Ungültige Eingabe", str(err))

        ctk.CTkButton(tab, text="Mit TinyPNG komprimieren", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    def start_tinypng_thread(
        self,
        api_key: str,
        input_folder: str,
        output_folder: str,
        should_resize: bool,
        max_size: tuple[int, int],
    ) -> None:
        """Startet die TinyPNG-Komprimierung in einem separaten Hintergrund-Thread."""
        threading.Thread(
            target=self.run_tinypng_compression,
            args=(api_key.strip(), input_folder, output_folder, should_resize, max_size),
            daemon=True,
        ).start()

    def run_tinypng_compression(
        self,
        api_key: str,
        input_folder: str,
        output_folder: str,
        should_resize: bool,
        max_size: tuple[int, int],
    ) -> None:
        """Führt die TinyPNG-Kompression über den Cloud-Dienst aus."""
        cleaned_key = api_key.strip()
        try:
            tinify.key = cleaned_key  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]
            tinify.validate()
            print("TinyPNG API-Key ist gültig.")
        except tinify.Error as e:
            self.after(
                0,
                lambda err=e: messagebox.showerror(
                    "TinyPNG Fehler",
                    f"Der API-Key ist ungültig oder es gab ein Verbindungsproblem:\n{err}",
                ),
            )
            return

        if should_resize:
            print(
                f"Größenanpassung via TinyPNG aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel."
            )

        def process(filename: str, in_folder: str, out_folder: str) -> None:
            safe_name = Path(filename).name
            input_path = (Path(in_folder).resolve() / safe_name).resolve()
            output_path = (Path(out_folder).resolve() / safe_name).resolve()
            try:
                compress_image_tinypng(input_path, output_path, should_resize, max_size)
            except tinify.Error as e:
                self.after(
                    0,
                    lambda err=e: messagebox.showwarning(
                        "TinyPNG Fehler",
                        f"Fehler bei '{safe_name}' (evtl. Monatslimit erreicht?):\n{err}",
                    ),
                )
                raise

        self._run_image_processing(
            "TinyPNG Komprimierung",
            input_folder,
            output_folder,
            SUPPORTED_EXTENSIONS_TINYPNG,
            process,
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
