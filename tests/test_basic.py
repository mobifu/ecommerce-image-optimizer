import re

from PIL import Image

import main


def test_app_constants():
    """Prüft, dass die grundlegenden App-Konstanten definiert und valide sind."""
    assert main.DEFAULT_INPUT_FOLDER == "Bilder_original"
    assert main.DEFAULT_OUTPUT_FOLDER == "Bilder_komprimiert"
    assert main.COMPANY_URL.startswith("https://")
    assert main.DONATE_URL.startswith("https://")
    assert Image.MAX_IMAGE_PIXELS == 120_000_000


def test_version_format():
    """Stellt sicher, dass VERSION_INFO dem Schema vX.Y.Z entspricht."""
    pattern = r"^v\d+\.\d+\.\d+$"
    assert re.match(pattern, main.VERSION_INFO) is not None
