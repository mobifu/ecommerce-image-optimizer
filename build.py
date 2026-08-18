import argparse  # NEU: Für Kommandozeilen-Argumente
import logging
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime

from Cython.Build import cythonize
from setuptools import Extension, setup

# Konfiguration
SOURCE_DIR = "."  # Stammverzeichnis des Python-Codes
MAIN_SCRIPT = "main.py"  # Hauptskript, das als Startpunkt für die Anwendung dient
APP_NAME = "bildkomprimierung"  # Name der ausführbaren Datei

# NEU: Dynamische Verzeichnisnamen mit Zeitstempel
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BUILD_TEMP = f"build_temp_{TIMESTAMP}"
DIST_DIR = f"dist_{TIMESTAMP}"

# --- NEU: Kommandozeilen-Parser ---
parser = argparse.ArgumentParser(description="Build-Skript für die Bildbearbeitungsanwendung.")
parser.add_argument(
    "--no-cython",
    action="store_true",
    help="Deaktiviert die Cython-Kompilierung für einen schnelleren Build.",
)

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# Funktion zum rekursiven Finden aller Python-Dateien
def find_all_python_files(directory):
    python_files = []
    # Verzeichnisse, die von der Suche ausgeschlossen werden sollen
    excluded_dirs = {BUILD_TEMP, DIST_DIR, "venv", ".git", "__pycache__", "hooks"}
    for root, dirs, files in os.walk(directory):
        # Modifiziere dirs an Ort und Stelle, um das Betreten der ausgeschlossenen Verzeichnisse zu verhindern
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


# Cython-Erweiterungen erstellen
def create_cython_extensions(python_files):
    extensions = []
    for py_file in python_files:
        # Normalisiere den Pfad, um führende './' oder '.\' zu entfernen
        normalized_path = os.path.normpath(py_file)
        if normalized_path.startswith("." + os.sep):
            normalized_path = normalized_path[2:]
        module_name = os.path.splitext(normalized_path)[0].replace(os.sep, ".")
        extensions.append(Extension(module_name, [py_file]))
    return extensions


# Funktion zum Beenden eines laufenden Prozesses (Windows-spezifisch)
def kill_process_if_running(process_name):
    """Versucht, einen Prozess anhand seines Namens zu beenden (plattformunabhängig)."""
    system = platform.system()
    if system == "Windows":
        # Windows verwendet .exe und taskkill
        process_name_os = f"{process_name}.exe"
        command = ["taskkill", "/F", "/IM", process_name_os]
    elif system == "Linux" or system == "Darwin":  # Darwin ist macOS
        # Linux/macOS haben keine .exe-Endung
        process_name_os = process_name
        command = ["pkill", "-f", process_name_os]
    else:
        logging.warning(
            f"Unbekanntes Betriebssystem '{system}'. Überspringe das Beenden des Prozesses."
        )
        return

    logging.info(f"Prüfe, ob '{process_name_os}' noch läuft und beende es bei Bedarf...")
    try:
        # Die Ausgabe wird umgeleitet, um die Konsole nicht mit Meldungen zu füllen.
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Befehl zum Beenden von '{process_name_os}' ausgeführt. Warte kurz...")
        time.sleep(2)
    except FileNotFoundError:
        logging.warning(
            f"Befehl '{command[0]}' nicht gefunden. Kann Prozess nicht automatisch beenden."
        )
    except Exception as e:
        logging.error(f"Fehler beim Versuch, den Prozess zu beenden: {e}")


# Temporäres Verzeichnis erstellen
def create_build_directories():
    os.makedirs(BUILD_TEMP, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)


# Alte Build-Dateien entfernen
def cleanup_build_files():
    """Entfernt alle alten Build-Verzeichnisse und temporären Dateien."""
    logging.info("Suche nach alten Build-Verzeichnissen (build, build_temp_*, dist_*)...")
    # Lösche alle alten build_temp_* und dist_* Ordner
    for item in os.listdir(SOURCE_DIR):
        if os.path.isdir(item) and (item.startswith("build_temp_") or item.startswith("dist_")):
            try:
                shutil.rmtree(item)
                logging.info(f"Altes Verzeichnis entfernt: {item}")
            except Exception as e:
                logging.error(f"Fehler beim Entfernen von {item}: {e}")

    # Lösche den Standard 'build'-Ordner von setuptools
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
            logging.info("Verzeichnis 'build' entfernt.")
        except Exception as e:
            logging.error(f"Fehler beim Entfernen von 'build': {e}")


# PyInstaller-Befehl erstellen
def create_pyinstaller_command(main_script, app_name):
    command = [
        "pyinstaller",
        "--onedir",
        "--name",
        app_name,
        "--windowed",  # Erstellt eine fensterbasierte Anwendung (ohne Konsole)
        "--clean",
        "--log-level",
        "INFO",
        main_script,
        "--distpath",
        DIST_DIR,
        "--workpath",
        BUILD_TEMP,
    ]
    if os.path.exists("public_key.pem"):
        command.extend(["--add-data", "public_key.pem;."])  # Fügt den öffentlichen Schlüssel hinzu

    # Fügt versteckte Importe hinzu, die für die Hardware-ID-Erkennung (oft via WMI) benötigt werden.
    # Dies ist ein häufiges Problem bei der Kompilierung mit PyInstaller.
    command.extend(["--hidden-import", "wmi"])
    command.extend(["--hidden-import", "pywin32.com.client"])

    # Fügt das licensing_module hinzu, damit es in der EXE verfügbar ist
    if os.path.exists("licensing_module"):
        command.extend(["--add-data", "licensing_module;licensing_module"])

    # Icon ist eine Windows-spezifische Option
    if platform.system() == "Windows":
        if os.path.exists("favicon.ico"):
            command.extend(["--add-data", "favicon.ico;.", "--icon", "favicon.ico"])

    return command


# Funktion zum Aufräumen nach dem Build
def final_cleanup():
    """Räumt nach dem erfolgreichen Build die temporären Dateien auf."""
    logging.info("Starte finales Aufräumen...")
    # Lösche den temporären Build-Ordner dieses Laufs
    if os.path.exists(BUILD_TEMP):
        shutil.rmtree(BUILD_TEMP)
        logging.info(f"Temporäres Verzeichnis '{BUILD_TEMP}' entfernt.")

    # Lösche den Standard 'build'-Ordner von setuptools
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
            logging.info("Verzeichnis 'build' entfernt.")
        except Exception as e:
            logging.error(f"Fehler beim Entfernen von 'build': {e}")

    # Lösche die .spec-Datei
    spec_file = f"{APP_NAME}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)
        logging.info(f"Spezifikationsdatei '{spec_file}' entfernt.")

    # NEU: Räume von Cython generierte .c und .pyd Dateien im Quellverzeichnis auf
    logging.info("Suche nach von Cython generierten Dateien (.c, .pyd) zum Entfernen...")
    deleted_cython_files_count = 0
    # Schließe die dynamisch erstellten Ordner von der Suche aus
    excluded_cleanup_dirs = {
        BUILD_TEMP,
        DIST_DIR,
        "venv",
        ".git",
        "__pycache__",
        "build",
    }
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Verhindere das Betreten der ausgeschlossenen Verzeichnisse
        dirs[:] = [d for d in dirs if d not in excluded_cleanup_dirs]
        # Bestimme die plattformspezifische Dateiendung für kompilierte Module
        compiled_ext = ".pyd" if platform.system() == "Windows" else ".so"
        for file in files:
            if file.endswith((".c", compiled_ext)):
                file_path = os.path.join(root, file)
                os.remove(file_path)
                deleted_cython_files_count += 1
                logging.debug(f"Entfernt: {file_path}")
    if deleted_cython_files_count > 0:
        logging.info(
            f"Insgesamt {deleted_cython_files_count} von Cython generierte Datei(en) entfernt."
        )


# Build-Prozess ausführen
def run_build_process(main_script, app_name, use_cython=True):
    try:
        if use_cython:
            logging.info("Build-Prozess wird MIT Cython-Kompilierung ausgeführt.")
        else:
            logging.info(
                "Build-Prozess wird OHNE Cython-Kompilierung ausgeführt (Option --no-cython)."
            )
        # 1. Aufräumen
        kill_process_if_running(app_name)

        # 2. Aufräumen
        logging.info("Starte Aufräumen alter Build-Dateien...")
        cleanup_build_files()

        # 3. Build-Verzeichnis erstellen
        logging.info("Erstelle Build-Verzeichnisse...")
        create_build_directories()

        if use_cython:
            # 4. Python-Dateien finden
            logging.info("Suche nach Python-Dateien für Cython...")
            python_files = find_all_python_files(SOURCE_DIR)

            # Das Build-Skript selbst von der Kompilierung ausschließen
            script_name = os.path.basename(__file__)
            python_files = [f for f in python_files if os.path.basename(f) != script_name]

            if not python_files:
                raise ValueError(
                    "Keine Python-Dateien im Quellverzeichnis gefunden (außer dem Build-Skript)."
                )

            # 5. Cython-Erweiterungen erstellen
            logging.info("Erstelle Cython-Erweiterungen...")
            extensions = create_cython_extensions(python_files)

            # 6. Setup-Funktion aufrufen, um die .c- und .so-Dateien zu erstellen
            logging.info("Starte Cython-Kompilierung...")
            setup(
                name=app_name,
                ext_modules=cythonize(extensions),
                script_args=["build_ext", "--inplace"],  # wichtig für korrekte Pfade
            )

        # 7. PyInstaller-Befehl erstellen
        logging.info("Erstelle PyInstaller-Befehl...")
        pyinstaller_command = create_pyinstaller_command(main_script, app_name)

        # 8. PyInstaller ausführen
        logging.info("Starte PyInstaller...")
        subprocess.check_call(pyinstaller_command)

        # 9. Finales Aufräumen
        final_cleanup()

        logging.info(f"Build abgeschlossen! Ausführbare Datei befindet sich in '{DIST_DIR}'.")

    except Exception as e:
        logging.error(f"Build fehlgeschlagen: {e}")


if __name__ == "__main__":
    args = parser.parse_args()
    # Führe den Build aus und übergebe, ob Cython verwendet werden soll
    run_build_process(MAIN_SCRIPT, APP_NAME, use_cython=not args.no_cython)
