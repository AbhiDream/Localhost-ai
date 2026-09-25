import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import sys

def test_tesseract():
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        version = pytesseract.get_tesseract_version()
        print(f'✓ Tesseract found: version {version}')
    except Exception as e:
        print(f'✗ Tesseract NOT found: {e}')
        sys.exit(1)

test_tesseract()
