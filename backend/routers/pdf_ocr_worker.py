"""Bounded local OCR worker for scanned PDF uploads.

This runs out-of-process so an OCR library failure cannot take down FastAPI.
It writes a single JSON object to stdout for the agent router to consume.
"""
import json
import sys


def main(pdf_path: str) -> None:
    import easyocr
    import numpy as np
    import pdfplumber

    reader = easyocr.Reader(["en"], gpu=False, verbose=False, download_enabled=False)
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        # Three low-resolution pages are enough for a demo and keep CPU/RAM
        # bounded. The user gets a clear evidence message for larger scans.
        for number, page in enumerate(pdf.pages[:3], start=1):
            image = page.to_image(resolution=110).original
            results = reader.readtext(np.array(image), workers=0)
            text = "\n".join(item[1] for item in results if item[2] >= 0.30)
            if text:
                pages.append(f"[Source: attached PDF, page {number}]\n{text}")
    print(json.dumps({"text": "\n\n".join(pages)}))


if __name__ == "__main__":
    main(sys.argv[1])
