import io
import hashlib
import pdfplumber
import fitz  # PyMuPDF
from typing import Tuple

class DocumentParserService:
    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        """
        Computes a deterministic cryptographic SHA-256 hash
        for BSA Section 63 digital integrity compliance.
        """
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        return hasher.hexdigest()

    @classmethod
    def extract_text_from_pdf(cls, file_bytes: bytes) -> Tuple[str, str]:
        """
        Extracts raw text from PDF bytes.
        Uses PyMuPDF first for speed, falling back to pdfplumber for complex layouts.
        Returns: (extracted_text, sha256_hash)
        """
        sha256_hash = cls.calculate_sha256(file_bytes)
        text_fragments = []

        # Tier A: High-speed extraction via PyMuPDF
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    page_text = page.get_text()
                    if page_text:
                        text_fragments.append(page_text)
        except Exception:
            pass

        full_text = "\n".join(text_fragments).strip()

        # Tier B: Fallback to pdfplumber if PyMuPDF extracted minimal text
        if len(full_text) < 50:
            text_fragments = []
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_fragments.append(page_text)
                full_text = "\n".join(text_fragments).strip()
            except Exception:
                pass

        return full_text, sha256_hash