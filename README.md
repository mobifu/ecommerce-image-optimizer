# 🖼️ Bildbearbeitungstool & Optimierer

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#lizenz)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)

Ein performantes, modernes Desktop-Tool (CustomTkinter) zur professionellen Stapelverarbeitung, Komprimierung und Konvertierung von Bilddateien (JPG, PNG, WebP) mit nativer TinyPNG-Cloud-Integration.

---

## 🚀 Features

- **Stapelverarbeitung (Batch Processing):** Verarbeitet ganze Ordnerstrukturen vollautomatisch im Hintergrund ohne GUI-Blockierung.
- **Lokale Komprimierung:**
  - Einstellbare Qualitätsstufen für JPEG (0–100 %).
  - Konfigurierbare Kompressionsstufen für PNG (0–9).
  - EXIF-Transposition für korrekte Ausrichtung.
- **Moderne WebP-Konvertierung:**
  - Konvertiert JPG- und PNG-Bilder in moderne, hochkomprimierte WebP-Assets für das Web.
- **Proportionale Skalierung:**
  - Automatische, aspektverhältnistreue Größenanpassung mit Maximalgrenzen (Thumbnail / Fit).
- **TinyPNG Cloud-Optimierung:**
  - Direkte Integration der TinyPNG-API für verlustarme Höchstkompression.
- **Echtzeit-Vorschau & Logging:**
  - Integrierte Thumbnail-Leiste und detailliertes Log-Terminal innerhalb der Benutzeroberfläche.
- **Enterprise-Sicherheit:**
  - Schutz vor Decompression-Bombs (`Image.MAX_IMAGE_PIXELS`).
  - Sichere Konfigurationshierarchie mit `.env`-Unterstützung und Ausschluss sensibler Secrets in `.gitignore`.
  - Absicherung aller Pfad-Operationen gegen Directory Traversal (`Path.resolve()`).

---

## 🛠️ Installation & Setup

### Voraussetzungen
- Python 3.10 oder neuer
- Optional: Virtuelle Umgebung (`venv`)

### 1. Repository klonen & Abhängigkeiten installieren
```bash
git clone <repository-url>
cd "Bild Berabeitung"

# Virtuelle Umgebung erstellen und aktivieren (Windows)
python -m venv venv
venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt
```

### 2. Konfiguration (Optional)
Kopieren Sie die Beispielkonfiguration oder `.env.example`:
```bash
copy .env.example .env
```
In der `.env`-Datei können API-Keys und Standardordner sicher hinterlegt werden:
```env
TINYPNG_API_KEY=dein_api_key_hier
COMP_SOURCE_DIR=Bilder_original
COMP_DEST_DIR=Bilder_komprimiert
```

---

## 💻 Anwendung starten

```bash
python main.py
```

---

## 📦 Standalone Executable erstellen (.exe)

Das integrierte Build-Skript erzeugt eine optimierte Standalone-Distribution via PyInstaller:

```bash
# Standard-Build (mit Cython-Optimierung):
python build.py

# Schneller Build ohne Cython:
python build.py --no-cython
```
Die fertige Anwendung wird im Verzeichnis `dist_<timestamp>/` abgelegt.

---

## 🧪 Qualitätssicherung & Tests

Das Projekt verfügt über eine vollständige automatisierte Test-Suite:

```bash
# Unit- und Sicherheitstests ausführen
pytest

# Testabdeckung prüfen
pytest --cov=. --cov-report=term-missing

# Security-Audit mit Bandit
bandit -r . -x ./sichern.py,./venv

# Code-Style & Linting mit Ruff
ruff check .
```

---

## 🔒 Sicherheitsrichtlinien (AppSec)

- **Secrets:** API-Keys werden nicht im Repository versioniert. Nutzen Sie `.env` oder tragen Sie den Key in die lokale `settings.json` ein (vollständig durch `.gitignore` geschützt).
- **Dateipfade:** Alle Ein- und Ausgabepfade werden streng über `pathlib.Path.resolve()` aufgelöst.
- **Bilddaten:** Grenzwerte für Bilddimensionen verhindern Denial-of-Service durch manipulierte Bilddateien.

---

## 📄 Lizenz & Kontakt

© Agentur Schölzke – [www.agentur-schoelzke.de](https://www.agentur-schoelzke.de)
