import io
import hashlib
import pdfplumber
from typing import Tuple

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from docx import Document
except ImportError:
    Document = None


class DocumentParserService:
    @staticmethod
    def calculate_sha3_256(file_bytes: bytes) -> str:
        """
        Computes a cryptographic SHA-3 (256-bit Keccak / FIPS 202) hash
        for modernized BSA Section 63 digital evidence compliance.
        """
        hasher = hashlib.sha3_256()
        hasher.update(file_bytes)
        return hasher.hexdigest()

    # Alias to keep any legacy references working smoothly
    calculate_sha256 = calculate_sha3_256

    @classmethod
    def extract_text(cls, file_bytes: bytes, filename: str) -> Tuple[str, str]:
        ext = filename.lower().split('.')[-1]
        sha3_hash = cls.calculate_sha3_256(file_bytes)
        
        if ext == "pdf":
            text = cls._extract_from_pdf(file_bytes)
        elif ext in ["docx", "doc"]:
            text = cls._extract_from_docx(file_bytes)
        elif ext in ["txt", "log", "json"]:
            text = file_bytes.decode("utf-8", errors="ignore")
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
            
        return text.strip(), sha3_hash

    @classmethod
    def _extract_from_pdf(cls, file_bytes: bytes) -> str:
        text_fragments = []
        if fitz:
            try:
                with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                    for page in doc:
                        page_text = page.get_text()
                        if page_text:
                            text_fragments.append(page_text)
            except Exception:
                pass

        full_text = "\n".join(text_fragments).strip()
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
        return full_text

    @classmethod
    def _extract_from_docx(cls, file_bytes: bytes) -> str:
        if not Document:
            return ""
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs if p.text])
        except Exception:
            return ""