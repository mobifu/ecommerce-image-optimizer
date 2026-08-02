import customtkinter as ctk
import os
import sys
from tkinter import filedialog, messagebox
import json
from PIL import Image, ImageOps
import tinify
import io
import threading
import webbrowser
from datetime import date

# Konstanten für Pfade und Einstellungen (können später in GUI geändert werden)
DEFAULT_INPUT_FOLDER = "Bilder_original"
DEFAULT_OUTPUT_FOLDER = "Bilder_komprimiert"

# --- Footer-Informationen ---
COMPANY_NAME = f"© Agentur Schölzke {date.today().year}"
COMPANY_URL = "https://www.agentur-schoelzke.de"
DONATE_URL = "https://paypal.me/kaischoelzke"
VERSION_INFO = "v1.10.0"  # Hier können Sie Ihre individuelle Versionsnummer eintragen


class TextboxLogger:
    """Leitet print-Ausgaben in ein CTkTextbox-Widget um."""

    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def flush(self):
        # Diese Methode wird von sys.stdout benötigt, kann aber leer bleiben.
        pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bildbearbeitungstool")
        self.geometry(
            "900x950"
        )  # Fensterhöhe erhöht, um alle Elemente sichtbar zu machen

        # Grid-Layout für flexible Größenanpassung
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Footer --- (Muss zuerst gepackt werden, um unten zu bleiben)
        self.create_footer()

        # Tabview erstellen
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tabview.add("Komprimieren")
        self.tabview.add("WebP Konvertieren")
        self.tabview.add("TinyPNG")

        # Tabs befüllen
        self.create_compression_tab()
        self.create_conversion_tab()
        self.create_tinypng_tab()

        # --- Fortschrittsanzeige (bleibt sichtbar) ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=(10, 0), fill="x")  # pady angepasst

        # --- Untere Tabview für Vorschau und Logs ---
        self.bottom_tabview = ctk.CTkTabview(self)
        self.bottom_tabview.pack(
            padx=20, pady=(10, 20), fill="x"
        )  # expand=True entfernt, damit dieser Bereich nicht zu viel Platz einnimmt

        self.bottom_tabview.add("Vorschau")
        self.bottom_tabview.add("Logs")

        # --- Thumbnail Vorschau ---
        self.thumbnail_frame = ctk.CTkScrollableFrame(
            self.bottom_tabview.tab("Vorschau"), label_text="Bildvorschau", height=150
        )
        self.thumbnail_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.thumbnail_frame.grid_columnconfigure(0, weight=1)

        # --- Log-Textfeld ---
        self.log_textbox = ctk.CTkTextbox(
            self.bottom_tabview.tab("Logs"), height=200, state="disabled"
        )
        self.log_textbox.pack(padx=10, pady=(10, 0), fill="x")

        # --- Button zum Leeren der Logs ---
        log_button_frame = ctk.CTkFrame(
            self.bottom_tabview.tab("Logs"), fg_color="transparent"
        )
        log_button_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(
            log_button_frame, text="Logs leeren", command=self.clear_logs
        ).pack(side="right")

        # --- stdout und stderr umleiten ---
        logger = TextboxLogger(self.log_textbox)
        sys.stdout = logger
        sys.stderr = logger

        # --- Einstellungen laden und Schließen-Verhalten festlegen ---
        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def clear_logs(self):
        """Leert das Log-Textfeld."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        print("Logs gelöscht.")

    def create_footer(self):
        """Erstellt den Footer mit Versionsinfo und Firmenlink."""
        footer_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        footer_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 10))

        version_label = ctk.CTkLabel(
            footer_frame, text=VERSION_INFO, text_color="gray60"
        )
        version_label.pack(side="left")

        company_label = ctk.CTkLabel(
            footer_frame, text=COMPANY_NAME, text_color="#1f6aa5", cursor="hand2"
        )
        company_label.pack(side="right")
        company_label.bind("<Button-1>", lambda e: self.open_url(COMPANY_URL))

        donate_label = ctk.CTkLabel(
            footer_frame, text="☕ Spenden", text_color="#1f6aa5", cursor="hand2"
        )
        donate_label.pack(side="right", padx=(0, 15))
        donate_label.bind("<Button-1>", lambda e: self.open_url(DONATE_URL))

    def open_url(self, url):
        """Öffnet eine URL im Standard-Webbrowser."""
        webbrowser.open_new(url)

    def select_folder(self, entry_widget, info_label=None, file_types=None):
        """Öffnet einen Dialog zur Ordnerauswahl und trägt den Pfad in das Entry-Widget ein."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, folder_path)
            if info_label and file_types:
                self.update_image_count(folder_path, info_label, file_types)
                self.update_thumbnails(folder_path, file_types)

    def update_image_count(self, folder_path, info_label, file_types):
        """Zählt die Bilder im Ordner und aktualisiert das Label."""
        try:
            if not os.path.isdir(folder_path):
                info_label.configure(text="Ordner nicht gefunden", text_color="orange")
                return

            count = sum(
                1 for f in os.listdir(folder_path) if f.lower().endswith(file_types)
            )
            info_label.configure(text=f"{count} Bild(er) gefunden", text_color="gray60")
        except Exception as e:
            info_label.configure(text="Fehler beim Lesen", text_color="red")
            print(f"Fehler beim Zählen der Bilder: {e}")
        self.update_idletasks()  # Erzwingt die sofortige Aktualisierung der GUI

    def update_thumbnails(self, folder_path, file_types):
        """Erstellt und zeigt Thumbnails für Bilder im ausgewählten Ordner an."""
        # Alte Thumbnails entfernen
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()

        try:
            if not os.path.isdir(folder_path):
                return

            files = [
                f for f in os.listdir(folder_path) if f.lower().endswith(file_types)
            ]

            # Wir begrenzen die Vorschau auf z.B. 50 Bilder, um die Performance zu wahren
            for filename in files[:50]:
                img_path = os.path.join(folder_path, filename)
                with Image.open(img_path) as img:
                    img = ImageOps.exif_transpose(img)  # EXIF-Drehung anwenden
                    img.thumbnail((100, 100))
                    # Wichtig: Das Image-Objekt muss referenziert bleiben, sonst wird es vom Garbage Collector gelöscht
                    ctk_img = ctk.CTkImage(light_image=img, size=img.size)
                    label = ctk.CTkLabel(self.thumbnail_frame, image=ctk_img, text="")
                    label.image = ctk_img  # Referenz speichern
                    label.pack(side="left", padx=5, pady=5)
        except Exception as e:
            print(f"Fehler beim Erstellen der Thumbnails: {e}")

    def save_settings(self):
        """Speichert die aktuellen Pfade und den API-Key in einer JSON-Datei."""
        settings = {
            "comp_source": self.comp_source_entry.get(),
            "comp_dest": self.comp_dest_entry.get(),
            "webp_source": self.webp_source_entry.get(),
            "webp_dest": self.webp_dest_entry.get(),
            "tinypng_source": self.tinypng_source_entry.get(),
            "tinypng_dest": self.tinypng_dest_entry.get(),
            "tinypng_api_key": self.tinypng_api_key_entry.get(),
        }
        try:
            with open("settings.json", "w") as f:
                json.dump(settings, f, indent=4)
            print("Einstellungen gespeichert.")
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")

    def load_settings(self):
        """Lädt Pfade und API-Key aus der JSON-Datei, falls vorhanden."""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    # Zuerst alle Felder leeren, um doppelte Einträge zu vermeiden
                    self.comp_source_entry.delete(0, "end")
                    self.comp_dest_entry.delete(0, "end")
                    self.webp_source_entry.delete(0, "end")
                    self.webp_dest_entry.delete(0, "end")
                    self.tinypng_source_entry.delete(0, "end")
                    self.tinypng_dest_entry.delete(0, "end")
                    self.tinypng_api_key_entry.delete(0, "end")

                    settings = json.load(f)
                    self.comp_source_entry.insert(
                        0, settings.get("comp_source", DEFAULT_INPUT_FOLDER)
                    )
                    self.comp_dest_entry.insert(
                        0, settings.get("comp_dest", DEFAULT_OUTPUT_FOLDER)
                    )
                    self.webp_source_entry.insert(
                        0, settings.get("webp_source", DEFAULT_INPUT_FOLDER)
                    )
                    self.webp_dest_entry.insert(
                        0, settings.get("webp_dest", "Bilder_webp")
                    )
                    self.tinypng_source_entry.insert(
                        0, settings.get("tinypng_source", DEFAULT_INPUT_FOLDER)
                    )
                    self.tinypng_dest_entry.insert(
                        0, settings.get("tinypng_dest", DEFAULT_OUTPUT_FOLDER)
                    )
                    self.tinypng_api_key_entry.insert(
                        0, settings.get("tinypng_api_key", "")
                    )

                    # Nach dem Laden die UI für den aktuell sichtbaren Tab aktualisieren
                    # Wir warten einen kurzen Moment, damit das Fenster sicher aufgebaut ist.
                    self.after(100, self.update_ui_for_current_tab)

                print("Einstellungen geladen.")
        except Exception as e:
            print(f"Fehler beim Laden der Einstellungen: {e}")

    def update_ui_for_current_tab(self):
        """Aktualisiert die Bildanzahl und Thumbnails für den aktuell ausgewählten Tab."""
        current_tab_name = self.tabview.get()
        if current_tab_name == "Komprimieren":
            self.update_image_count(
                self.comp_source_entry.get(),
                self.comp_source_info_label,
                (".jpg", ".jpeg", ".png"),
            )
            self.update_thumbnails(
                self.comp_source_entry.get(), (".jpg", ".jpeg", ".png")
            )
        elif current_tab_name == "WebP Konvertieren":
            self.update_image_count(
                self.webp_source_entry.get(),
                self.webp_source_info_label,
                (".png", ".jpg", ".jpeg"),
            )
            self.update_thumbnails(
                self.webp_source_entry.get(), (".png", ".jpg", ".jpeg")
            )
        elif current_tab_name == "TinyPNG":
            self.update_image_count(
                self.tinypng_source_entry.get(),
                self.tinypng_source_info_label,
                (".png", ".jpg", ".jpeg"),
            )
            self.update_thumbnails(
                self.tinypng_source_entry.get(), (".png", ".jpg", ".jpeg")
            )

    def on_closing(self):
        """Wird aufgerufen, wenn das Fenster geschlossen wird."""
        self.save_settings()
        self.destroy()

    def _create_folder_selection_block(
        self,
        parent_tab,
        label_text,
        entry_attr_name,
        info_label_attr_name=None,
        file_types=None,
        is_source=True,
    ):
        """
        Erstellt einen UI-Block für die Auswahl eines Quell- oder Zielordners.
        Weist die erstellten Widgets den entsprechenden Attributen der App-Instanz zu.
        """
        frame = ctk.CTkFrame(parent_tab)
        frame.pack(padx=20, pady=(10, 5) if is_source else (0, 5), fill="x")
        ctk.CTkLabel(frame, text=label_text).pack(
            anchor="w", padx=10, pady=(5, 0) if is_source else (10, 0)
        )

        input_controls_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_controls_frame.pack(fill="x", padx=10, pady=(0, 5))

        entry_widget = ctk.CTkEntry(input_controls_frame)
        entry_widget.pack(side="left", fill="x", expand=True)
        setattr(self, entry_attr_name, entry_widget)  # Widget als Attribut speichern

        if is_source:
            info_label = ctk.CTkLabel(frame, text="")
            info_label.pack(anchor="w", padx=10, pady=(0, 5))
            setattr(
                self, info_label_attr_name, info_label
            )  # Info-Label als Attribut speichern

            def browse_command():
                return self.select_folder(entry_widget, info_label, file_types)

        else:

            def browse_command():
                return self.select_folder(entry_widget)

        browse_button = ctk.CTkButton(
            input_controls_frame, text="Durchsuchen...", command=browse_command
        )
        browse_button.pack(side="right", padx=(5, 0))

    def _create_resize_options_block(
        self, parent_tab, check_attr_name, width_attr_name, height_attr_name
    ):
        """
        Erstellt einen UI-Block für die Größenanpassungsoptionen.
        Weist die erstellten Widgets den entsprechenden Attributen der App-Instanz zu.
        """
        resize_frame = ctk.CTkFrame(parent_tab)
        resize_frame.pack(padx=20, pady=10, fill="x")

        resize_check = ctk.CTkCheckBox(
            resize_frame, text="Bildgröße anpassen (proportional)"
        )
        resize_check.pack(anchor="w", padx=10, pady=10)
        setattr(self, check_attr_name, resize_check)  # Checkbox als Attribut speichern

        size_inner_frame = ctk.CTkFrame(resize_frame, fg_color="transparent")
        size_inner_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(size_inner_frame, text="Max. Breite:").pack(side="left")
        width_entry = ctk.CTkEntry(size_inner_frame, width=80)
        width_entry.pack(side="left", padx=(5, 20))
        width_entry.insert(0, "1024")
        setattr(
            self, width_attr_name, width_entry
        )  # Breite-Entry als Attribut speichern

        ctk.CTkLabel(size_inner_frame, text="Max. Höhe:").pack(side="left")
        height_entry = ctk.CTkEntry(size_inner_frame, width=80)
        height_entry.pack(side="left", padx=5)
        height_entry.insert(0, "1024")
        setattr(
            self, height_attr_name, height_entry
        )  # Höhe-Entry als Attribut speichern

    def create_compression_tab(self):
        """Erstellt den Tab für die Komprimierungsfunktion."""
        tab = self.tabview.tab("Komprimieren")

        # --- Quellordner ---
        self._create_folder_selection_block(
            tab,
            "Quellordner (JPG, JPEG, PNG)",
            "comp_source_entry",
            "comp_source_info_label",
            (".jpg", ".jpeg", ".png"),
            is_source=True,
        )
        self._create_folder_selection_block(
            tab, "Zielordner:", "comp_dest_entry", is_source=False
        )

        # --- Einstellungen ---
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=10, fill="x")
        settings_frame.grid_columnconfigure(1, weight=1)  # Slider soll sich ausdehnen

        ctk.CTkLabel(settings_frame, text="Qualität (nur JPG):").grid(
            row=0, column=0, padx=(10, 5), pady=10
        )

        self.comp_quality_slider = ctk.CTkSlider(
            settings_frame, from_=0, to=100, command=self.update_quality_from_slider
        )
        self.comp_quality_slider.set(75)  # Standardwert
        self.comp_quality_slider.grid(row=0, column=1, sticky="ew", padx=5, pady=10)

        self.comp_quality_entry = ctk.CTkEntry(settings_frame, width=50)
        self.comp_quality_entry.insert(0, "75")
        self.comp_quality_entry.grid(row=0, column=2, padx=5, pady=10)
        # Binden des Events, um den Slider zu aktualisieren, wenn die Eingabe abgeschlossen ist (Enter oder Fokusverlust)
        self.comp_quality_entry.bind("<Return>", self.update_quality_from_entry)
        self.comp_quality_entry.bind("<FocusOut>", self.update_quality_from_entry)

        ctk.CTkLabel(settings_frame, text="%").grid(
            row=0, column=3, padx=(0, 10), pady=10
        )

        # NEU: PNG Komprimierungsstufe
        ctk.CTkLabel(settings_frame, text="Kompression (nur PNG):").grid(
            row=1, column=0, padx=(10, 5), pady=10
        )

        self.comp_png_level_slider = ctk.CTkSlider(
            settings_frame,
            from_=0,
            to=9,
            number_of_steps=9,
            command=self.update_png_level_from_slider,
        )
        self.comp_png_level_slider.set(6)  # Guter Standardwert
        self.comp_png_level_slider.grid(row=1, column=1, sticky="ew", padx=5, pady=10)

        self.comp_png_level_entry = ctk.CTkEntry(settings_frame, width=50)
        self.comp_png_level_entry.insert(0, "6")
        self.comp_png_level_entry.grid(row=1, column=2, padx=5, pady=10)
        self.comp_png_level_entry.bind("<Return>", self.update_png_level_from_entry)
        self.comp_png_level_entry.bind("<FocusOut>", self.update_png_level_from_entry)

        ctk.CTkLabel(settings_frame, text="(0-9)").grid(
            row=1, column=3, padx=(0, 10), pady=10
        )

        # --- Größenanpassung ---
        self._create_resize_options_block(
            tab, "comp_resize_check", "comp_width_entry", "comp_height_entry"
        )

        # --- Threading-Wrapper für den Start (jetzt sind alle Widgets bekannt) ---
        def start_thread():
            try:
                png_level = int(self.comp_png_level_entry.get())
                quality = int(
                    self.comp_quality_entry.get()
                )  # Wert aus dem Entry-Feld nehmen
                max_size = (
                    int(self.comp_width_entry.get()),
                    int(self.comp_height_entry.get()),
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
            except ValueError:
                messagebox.showerror(
                    "Ungültige Eingabe",
                    "Bitte geben Sie für Breite und Höhe nur ganze Zahlen ein.",
                )

        # --- Start Button ---
        ctk.CTkButton(tab, text="Komprimierung starten", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    def update_quality_from_slider(self, value):
        """Aktualisiert das Eingabefeld, wenn der JPG-Slider bewegt wird."""
        self.comp_quality_entry.delete(0, "end")
        self.comp_quality_entry.insert(0, str(int(value)))

    def update_quality_from_entry(self, event):
        """Aktualisiert den JPG-Slider, wenn im Eingabefeld ein Wert eingegeben wird."""
        try:
            value = int(self.comp_quality_entry.get())
            if 0 <= value <= 100:
                self.comp_quality_slider.set(value)
            else:  # Korrigiert den Wert, wenn er außerhalb des Bereichs liegt
                value = max(0, min(100, value))
                self.comp_quality_entry.delete(0, "end")
                self.comp_quality_entry.insert(0, str(value))
                self.comp_quality_slider.set(value)
        except (ValueError, TypeError):  # Ignoriert ungültige Eingaben
            pass

    def update_png_level_from_slider(self, value):
        """Aktualisiert das Eingabefeld, wenn der PNG-Slider bewegt wird."""
        self.comp_png_level_entry.delete(0, "end")
        self.comp_png_level_entry.insert(0, str(int(value)))

    def update_png_level_from_entry(self, event):
        """Aktualisiert den PNG-Slider, wenn im Eingabefeld ein Wert eingegeben wird."""
        try:
            value = int(self.comp_png_level_entry.get())
            if 0 <= value <= 9:
                self.comp_png_level_slider.set(value)
            else:  # Korrigiert den Wert, wenn er außerhalb des Bereichs liegt
                value = max(0, min(9, value))
                self.comp_png_level_entry.delete(0, "end")
                self.comp_png_level_entry.insert(0, str(value))
                self.comp_png_level_slider.set(value)
        except (ValueError, TypeError):  # Ignoriert ungültige Eingaben
            pass

    def _run_image_processing(
        self,
        task_name,
        input_folder,
        output_folder,
        file_types,
        process_function,
        show_completion_message=True,
    ):
        """
        Eine generische Methode zur Verarbeitung von Bilddateien in einem Ordner.
        Sie kümmert sich um Validierung, Dateisuche, Fortschrittsanzeige und Fehlerbehandlung.
        """
        print(f"Starte Aufgabe: {task_name} für Ordner '{input_folder}'")

        if os.path.normpath(input_folder) == os.path.normpath(output_folder):
            if not messagebox.askyesno(
                "Warnung",
                "Quell- und Zielordner sind identisch. Das wird Ihre Originaldateien überschreiben!\n\nMöchten Sie wirklich fortfahren?",
            ):
                print("Vorgang vom Benutzer abgebrochen.")
                return

        try:
            if not os.path.isdir(input_folder):
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Fehler",
                        f"Der Quellordner wurde nicht gefunden:\n{input_folder}",
                    ),
                )
                return

            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

            files = [
                f for f in os.listdir(input_folder) if f.lower().endswith(file_types)
            ]
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
                    # Die eigentliche Verarbeitungslogik wird hier aufgerufen
                    process_function(filename, input_folder, output_folder)
                except Exception as e:
                    print(f"Fehler bei der Verarbeitung von {filename}: {e}")
                    # Bei TinyPNG-Fehlern, die eine Messagebox zeigen, hier abbrechen
                    if "tinify.Error" in str(type(e)):
                        self.after(
                            0, lambda: self.progress_bar.set(0)
                        )  # Fortschritt zurücksetzen
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
                lambda e=e: messagebox.showerror(
                    "Unerwarteter Fehler", f"Ein Fehler ist aufgetreten:\n{e}"
                ),
            )
        finally:
            # Fortschrittsbalken nach Abschluss (oder Fehler) zurücksetzen
            self.after(100, lambda: self.progress_bar.set(0))

    def run_compression(
        self, input_folder, output_folder, quality, png_level, should_resize, max_size
    ):
        """Startet den lokalen Komprimierungsprozess für JPG und PNG."""
        if should_resize:
            print(
                f"Größenanpassung aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel."
            )

        def process(filename, in_folder, out_folder):
            img_path = os.path.join(in_folder, filename)
            with Image.open(img_path) as img:
                img = ImageOps.exif_transpose(img)  # EXIF-Drehung anwenden
                if should_resize:
                    img.thumbnail(max_size)
                if filename.lower().endswith((".jpg", ".jpeg")):
                    img.save(
                        os.path.join(out_folder, filename),
                        "JPEG",
                        quality=quality,
                        optimize=True,
                    )
                    print(f"Komprimiert (JPG): {filename}")
                elif filename.lower().endswith(".png"):
                    img.save(
                        os.path.join(out_folder, filename),
                        "PNG",
                        optimize=True,
                        compress_level=png_level,
                    )
                    print(f"Komprimiert (PNG): {filename}")

        self._run_image_processing(
            "Lokale Komprimierung",
            input_folder,
            output_folder,
            (".jpg", ".jpeg", ".png"),
            process,
        )

    def create_conversion_tab(self):
        """Erstellt den Tab für die Konvertierungsfunktionen."""
        tab = self.tabview.tab("WebP Konvertieren")

        # --- Quellordner ---
        self._create_folder_selection_block(
            tab,
            "Quellordner (PNG, JPG)",
            "webp_source_entry",
            "webp_source_info_label",
            (".png", ".jpg", ".jpeg"),
            is_source=True,
        )
        self._create_folder_selection_block(
            tab, "Zielordner:", "webp_dest_entry", is_source=False
        )

        # --- Einstellungen (Qualität) ---
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=10, fill="x")
        settings_frame.grid_columnconfigure(1, weight=1)  # Slider soll sich ausdehnen

        ctk.CTkLabel(settings_frame, text="Qualität (nur WebP):").grid(
            row=0, column=0, padx=(10, 5), pady=10
        )

        self.webp_quality_slider = ctk.CTkSlider(
            settings_frame,
            from_=0,
            to=100,
            command=self.update_webp_quality_from_slider,
        )
        self.webp_quality_slider.set(80)
        self.webp_quality_slider.grid(row=0, column=1, sticky="ew", padx=5, pady=10)

        self.webp_quality_entry = ctk.CTkEntry(settings_frame, width=50)
        self.webp_quality_entry.insert(0, "80")
        self.webp_quality_entry.grid(row=0, column=2, padx=5, pady=10)
        self.webp_quality_entry.bind("<Return>", self.update_webp_quality_from_entry)
        self.webp_quality_entry.bind("<FocusOut>", self.update_webp_quality_from_entry)

        ctk.CTkLabel(settings_frame, text="%").grid(
            row=0, column=3, padx=(0, 10), pady=10
        )

        # --- Größenanpassung ---
        self._create_resize_options_block(
            tab, "webp_resize_check", "webp_width_entry", "webp_height_entry"
        )

        # --- Threading-Wrapper für den Start ---
        def start_thread():
            try:
                quality = int(
                    self.webp_quality_entry.get()
                )  # Wert aus dem Entry-Feld nehmen
                max_size = (
                    int(self.webp_width_entry.get()),
                    int(self.webp_height_entry.get()),
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
            except ValueError:
                messagebox.showerror(
                    "Ungültige Eingabe",
                    "Bitte geben Sie für Breite und Höhe nur ganze Zahlen ein.",
                )

        # --- Start Button ---
        ctk.CTkButton(tab, text="Nach WebP konvertieren", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    def update_webp_quality_from_slider(self, value):
        """Aktualisiert das Eingabefeld, wenn der WebP-Slider bewegt wird."""
        self.webp_quality_entry.delete(0, "end")
        self.webp_quality_entry.insert(0, str(int(value)))

    def update_webp_quality_from_entry(self, event):
        """Aktualisiert den WebP-Slider, wenn im Eingabefeld ein Wert eingegeben wird."""
        try:
            value = int(self.webp_quality_entry.get())
            if 0 <= value <= 100:
                self.webp_quality_slider.set(value)
            else:  # Korrigiert den Wert, wenn er außerhalb des Bereichs liegt
                value = max(0, min(100, value))
                self.webp_quality_entry.delete(0, "end")
                self.webp_quality_entry.insert(0, str(value))
                self.webp_quality_slider.set(value)
        except (ValueError, TypeError):  # Ignoriert ungültige Eingaben
            pass

    def run_webp_conversion(
        self, input_folder, output_folder, quality, should_resize, max_size
    ):
        """Führt die Logik aus umwandeln-webp.py aus."""
        if should_resize:
            print(
                f"Größenanpassung aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel."
            )

        def process(filename, in_folder, out_folder):
            file_path = os.path.join(in_folder, filename)
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)  # EXIF-Drehung anwenden
                if should_resize:
                    img.thumbnail(max_size)
                output_file_path = os.path.join(
                    out_folder, f"{os.path.splitext(filename)[0]}.webp"
                )
                img.save(output_file_path, "WEBP", quality=quality)
                print(
                    f"Konvertiert: {filename} -> {os.path.basename(output_file_path)}"
                )

        self._run_image_processing(
            "WebP Konvertierung",
            input_folder,
            output_folder,
            (".png", ".jpg", ".jpeg"),
            process,
        )

    def create_tinypng_tab(self):
        """Erstellt den Tab für die TinyPNG-Funktionen."""
        tab = self.tabview.tab("TinyPNG")

        # --- API Key ---
        ctk.CTkLabel(tab, text="TinyPNG API Key:").pack(padx=20, pady=(10, 0))
        self.tinypng_api_key_entry = ctk.CTkEntry(tab, width=400, show="*")
        self.tinypng_api_key_entry.pack(
            padx=20, pady=5
        )  # Der Key wird jetzt nur noch aus der settings.json geladen

        # --- Quellordner ---
        self._create_folder_selection_block(
            tab,
            "Quellordner (PNG, JPG)",
            "tinypng_source_entry",
            "tinypng_source_info_label",
            (".png", ".jpg", ".jpeg"),
            is_source=True,
        )
        self._create_folder_selection_block(
            tab, "Zielordner:", "tinypng_dest_entry", is_source=False
        )

        # --- Größenanpassung ---
        self._create_resize_options_block(
            tab, "tinypng_resize_check", "tinypng_width_entry", "tinypng_height_entry"
        )

        # --- Start Button ---
        def start_thread():
            api_key = self.tinypng_api_key_entry.get()
            if not api_key:
                messagebox.showerror("Fehler", "Bitte gib einen TinyPNG API-Key ein.")
                return
            try:
                max_size = (
                    int(self.tinypng_width_entry.get()),
                    int(self.tinypng_height_entry.get()),
                )
                self.start_tinypng_thread(
                    api_key,
                    self.tinypng_source_entry.get(),
                    self.tinypng_dest_entry.get(),
                    self.tinypng_resize_check.get(),
                    max_size,
                )
            except ValueError:
                messagebox.showerror(
                    "Ungültige Eingabe",
                    "Bitte geben Sie für Breite und Höhe nur ganze Zahlen ein.",
                )

        ctk.CTkButton(tab, text="Mit TinyPNG komprimieren", command=start_thread).pack(
            anchor="w", padx=20, pady=20
        )

    def start_tinypng_thread(
        self, api_key, input_folder, output_folder, should_resize, max_size
    ):
        """Startet die TinyPNG-Komprimierung in einem separaten Thread, um die GUI nicht zu blockieren."""
        # Die Verarbeitung wird in einem neuen Thread gestartet
        thread = threading.Thread(
            target=self.run_tinypng_compression,
            args=(api_key, input_folder, output_folder, should_resize, max_size),
            daemon=True,
        )
        thread.start()

    def run_tinypng_compression(
        self, api_key, input_folder, output_folder, should_resize, max_size
    ):
        """Führt die Logik aus tinypng-kompress.py aus."""
        try:
            tinify.key = api_key
            tinify.validate()
            print("TinyPNG API-Key ist gültig.")
        except tinify.Error as e:
            self.after(
                0,
                lambda e=e: messagebox.showerror(
                    "TinyPNG Fehler",
                    f"Der API-Key ist ungültig oder es gab ein Verbindungsproblem:\n{e}",
                ),
            )
            return

        if should_resize:
            print(
                f"Größenanpassung via TinyPNG aktiviert. Maximale Größe: {max_size[0]}x{max_size[1]} Pixel."
            )

        def process(filename, in_folder, out_folder):
            input_path = os.path.join(in_folder, filename)
            output_path = os.path.join(out_folder, filename)
            print(f"Komprimiere: {filename} ...")

            # Bild mit Pillow öffnen, um EXIF-Drehung anzuwenden, und in einem Puffer speichern
            with Image.open(input_path) as img:
                img = ImageOps.exif_transpose(img)  # EXIF-Drehung anwenden

                # Das Format (JPEG/PNG) für die Speicherung im Puffer beibehalten
                img_format = img.format or (
                    "JPEG" if filename.lower().endswith((".jpg", ".jpeg")) else "PNG"
                )

                buffer = io.BytesIO()
                img.save(buffer, format=img_format)
                buffer.seek(0)
                source = tinify.from_buffer(buffer.read())

            try:
                if should_resize:
                    resized = source.resize(
                        method="fit", width=max_size[0], height=max_size[1]
                    )
                    resized.to_file(output_path)
                else:
                    source.to_file(output_path)
                print(f"Fertig: {filename} gespeichert in {out_folder}")
            except tinify.Error as e:
                self.after(
                    0,
                    lambda err=e: messagebox.showwarning(
                        "TinyPNG Fehler",
                        f"Fehler bei '{filename}' (evtl. Monatslimit erreicht?):\n{err}",
                    ),
                )
                raise e  # Wirft den Fehler erneut, damit die Hauptschleife ihn fangen und abbrechen kann

        self._run_image_processing(
            "TinyPNG Komprimierung",
            input_folder,
            output_folder,
            (".png", ".jpg", ".jpeg"),
            process,
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
