# Bildbearbeitungstool

Ein Python-basiertes GUI-Tool (CustomTkinter) zur Komprimierung von Bildern (JPG, PNG) sowie Konvertierung nach WebP und Anbindung an TinyPNG.

## Features
- Lokale Komprimierung von JPG- und PNG-Dateien
- Proportionale Bildgrößenanpassung
- Konvertierung von PNG/JPG nach WebP
- Erstellung einer Standalone-Executable (.exe) via PyInstaller (`build.py`)

## Ausführung
```bash
python main.py
```

## Build-Prozess (Executable erstellen)
Das Build-Skript unterstützt das Paketieren als Verzeichnis (`--onedir`) für optimale Startzeiten.

```bash
python build.py
```
*Optional ohne Cython:*
```bash
python build.py --no-cython
```

## Tests ausführen
Das Projekt verwendet `pytest` für automatisierte Tests:

```bash
python -m pytest --cov=. --cov-report=term-missing
```
