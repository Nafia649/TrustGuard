import io
import logging
import os
from typing import List, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

# Optional PyMuPDF (fitz) for high-performance PDF processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF (fitz) is not installed. PDF text extraction may be limited.")

# Optional pytesseract for raster OCR
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract is not installed. Scanned document OCR is disabled.")


class OCREngine:
    """
    Document extraction abstraction layer.
    Strategy:
    1. Attempt direct high-fidelity text extraction for text-based PDFs (PyMuPDF).
    2. If text is sparse / scanned or if input is an image, fall back to Tesseract OCR if installed.
    3. If Tesseract binary is not installed on the host system, return informative warning.
    """

    def is_tesseract_installed(self) -> bool:
        if not PYTESSERACT_AVAILABLE:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_text(self, file_path: str, file_type: str) -> Tuple[str, float, List[str]]:
        """
        Extracts raw text, base confidence, and warnings from a document.
        Returns: (raw_text, confidence, warnings)
        """
        if not os.path.exists(file_path):
            return "", 0.0, [f"File not found: {file_path}"]

        ext = os.path.splitext(file_path)[1].lower()
        warnings: List[str] = []

        if ext == ".pdf" or "pdf" in file_type.lower():
            return self._extract_pdf(file_path, warnings)
        elif ext in [".png", ".jpg", ".jpeg"] or "image" in file_type.lower():
            return self._extract_image(file_path, warnings)
        else:
            return "", 0.0, [f"Unsupported document type: {file_type} ({ext})"]

    def _extract_pdf(self, file_path: str, warnings: List[str]) -> Tuple[str, float, List[str]]:
        text_content = []
        is_scanned = False

        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    page_text = page.get_text("text")
                    if page_text and len(page_text.strip()) > 10:
                        text_content.append(page_text)
                    else:
                        # Page has little or no embedded text; might be scanned
                        is_scanned = True

                doc.close()
            except Exception as e:
                warnings.append(f"PyMuPDF error reading PDF: {str(e)}")
        else:
            # Fallback to pypdf if PyMuPDF unavailable
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                for page in reader.pages:
                    p_text = page.extract_text() or ""
                    if len(p_text.strip()) > 10:
                        text_content.append(p_text)
                    else:
                        is_scanned = True
            except Exception as e:
                warnings.append(f"pypdf error reading PDF: {str(e)}")

        combined_text = "\n".join(text_content).strip()

        # If direct text extraction produced adequate content (> 30 characters)
        if len(combined_text) >= 30:
            return combined_text, 0.95, warnings

        # If PDF is scanned or image-based, attempt OCR fallback
        if is_scanned or len(combined_text) < 30:
            warnings.append("Document appears to be a scanned or image-based PDF.")
            if self.is_tesseract_installed() and PYMUPDF_AVAILABLE:
                try:
                    ocr_text = []
                    doc = fitz.open(file_path)
                    for page in doc:
                        pix = page.get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        page_ocr = pytesseract.image_to_string(img)
                        ocr_text.append(page_ocr)
                    doc.close()
                    combined_ocr = "\n".join(ocr_text).strip()
                    if combined_ocr:
                        return combined_ocr, 0.85, warnings
                except Exception as e:
                    warnings.append(f"OCR rasterization failed: {str(e)}")
            else:
                warnings.append(
                    "Tesseract OCR executable is not available on host system for scanned PDF OCR."
                )

        return combined_text, (0.50 if combined_text else 0.0), warnings

    def _extract_image(self, file_path: str, warnings: List[str]) -> Tuple[str, float, List[str]]:
        if not self.is_tesseract_installed():
            warnings.append(
                "Image invoice uploaded, but Tesseract OCR executable is not installed on system PATH."
            )
            return "", 0.0, warnings

        try:
            img = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(img).strip()
            confidence = 0.88 if len(ocr_text) > 30 else 0.40
            return ocr_text, confidence, warnings
        except Exception as e:
            warnings.append(f"Image OCR failed: {str(e)}")
            return "", 0.0, warnings


ocr_engine = OCREngine()
