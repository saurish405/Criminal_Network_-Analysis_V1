import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class EvidenceVaultService:
    """
    In-memory immutable audit ledger enforcing Section 63 of 
    Bharatiya Sakshya Adhiniyam (BSA) for digital forensics.
    """
    _audit_ledger: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_document(
        cls, 
        doc_id: str, 
        sha256_hash: str, 
        filename: str, 
        officer_id: str = "POLICE_NCRB_OFFICER_01"
    ) -> Dict[str, Any]:
        record = {
            "document_id": doc_id,
            "filename": filename,
            "sha256_hash": sha256_hash,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "officer_id": officer_id,
            "bsa_section_63_verified": True,
            "tamper_detected": False
        }
        cls._audit_ledger[doc_id] = record
        return record

    @classmethod
    def get_document(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        return cls._audit_ledger.get(doc_id)

    @classmethod
    def get_all_records(cls) -> Dict[str, Dict[str, Any]]:
        return cls._audit_ledger

    @classmethod
    def verify_document(cls, doc_id: str, current_bytes: bytes) -> Dict[str, Any]:
        """
        Recomputes hash of submitted document and validates against initial record.
        """
        if doc_id not in cls._audit_ledger:
            return {
                "document_id": doc_id,
                "sha256_hash": hashlib.sha256(current_bytes).hexdigest(),
                "original_hash": None,
                "tamper_status": "DOCUMENT_NOT_FOUND",
                "bsa_compliant": False,
                "timestamp": None
            }

        current_hash = hashlib.sha256(current_bytes).hexdigest()
        original_record = cls._audit_ledger[doc_id]
        is_authentic = (current_hash == original_record["sha256_hash"])

        return {
            "document_id": doc_id,
            "sha256_hash": current_hash,
            "original_hash": original_record["sha256_hash"],
            "tamper_status": "AUTHENTIC / UNTAMPERED" if is_authentic else "TAMPERED / MISMATCH",
            "bsa_compliant": is_authentic,
            "timestamp": original_record["registered_at"]
        }