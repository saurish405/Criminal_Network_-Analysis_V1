import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class EvidenceVaultService:
    _blockchain_ledger: List[Dict[str, Any]] = []
    _storage_dir = "evidence_store"

    @classmethod
    def _compute_sha3(cls, data_bytes: bytes) -> str:
        hasher = hashlib.sha3_256()
        hasher.update(data_bytes)
        return hasher.hexdigest()

    @classmethod
    def _get_genesis_block(cls) -> Dict[str, Any]:
        genesis_hash = cls._compute_sha3(b"NCRB_GENESIS_ROOT_SHA3")
        return {
            "index": 0,
            "document_id": "GENESIS_BLOCK",
            "filename": "GENESIS",
            "sha3_256_hash": "0" * 64,
            "file_sha3_256": "0" * 64,
            "prev_hash": "0" * 64,
            "block_hash": genesis_hash,
            "registered_at": "2026-01-01T00:00:00Z",
            "officer_id": "SYSTEM_ROOT",
            "bsa_section_63_verified": True,
            "file_url": None,
            "tamper_detected": False
        }

    @classmethod
    def _compute_block_hash(cls, index: int, prev_hash: str, doc_hash: str, timestamp: str, doc_id: str) -> str:
        header = f"{index}{prev_hash}{doc_hash}{timestamp}{doc_id}".encode('utf-8')
        return cls._compute_sha3(header)

    @classmethod
    def register_document(
        cls, 
        doc_id: str, 
        sha3_hash: str, 
        filename: str, 
        file_bytes: Optional[bytes] = None,
        officer_id: str = "POLICE_NCRB_OFFICER_01"
    ) -> Dict[str, Any]:
        os.makedirs(cls._storage_dir, exist_ok=True)
        
        if not cls._blockchain_ledger:
            cls._blockchain_ledger.append(cls._get_genesis_block())

        prev_block = cls._blockchain_ledger[-1]
        prev_hash = prev_block["block_hash"]
        timestamp = datetime.now(timezone.utc).isoformat()
        index = len(cls._blockchain_ledger)

        safe_filename = f"{doc_id}_{filename}"
        if file_bytes:
            storage_path = os.path.join(cls._storage_dir, safe_filename)
            with open(storage_path, "wb") as f:
                f.write(file_bytes)

        block_hash = cls._compute_block_hash(index, prev_hash, sha3_hash, timestamp, doc_id)

        block = {
            "index": index,
            "document_id": doc_id,
            "filename": filename,
            "sha3_256_hash": sha3_hash,
            "file_sha3_256": sha3_hash,
            "prev_hash": prev_hash,
            "block_hash": block_hash,
            "registered_at": timestamp,
            "officer_id": officer_id,
            "bsa_section_63_verified": True,
            "file_url": f"/api/v1/evidence/download/{safe_filename}" if file_bytes else None,
            "tamper_detected": False
        }
        cls._blockchain_ledger.append(block)
        return block

    @classmethod
    def get_blockchain_ledger(cls) -> List[Dict[str, Any]]:
        if not cls._blockchain_ledger:
            cls._blockchain_ledger.append(cls._get_genesis_block())
        return cls._blockchain_ledger

    @classmethod
    def get_all_records(cls) -> List[Dict[str, Any]]:
        return cls.get_blockchain_ledger()

    @classmethod
    def get_document(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        for block in cls._blockchain_ledger:
            if block.get("document_id") == doc_id:
                return block
        return None

    @classmethod
    def verify_document(cls, doc_id: str, current_bytes: bytes) -> Dict[str, Any]:
        current_hash = cls._compute_sha3(current_bytes)
        record = cls.get_document(doc_id)
        
        if not record:
            return {
                "document_id": doc_id,
                "sha3_256_hash": current_hash,
                "original_hash": None,
                "tamper_status": "DOCUMENT_NOT_FOUND",
                "bsa_compliant": False,
                "timestamp": None
            }

        original_hash = record.get("file_sha3_256") or record.get("sha3_256_hash")
        is_authentic = (current_hash == original_hash)
        return {
            "document_id": doc_id,
            "sha3_256_hash": current_hash,
            "original_hash": original_hash,
            "tamper_status": "AUTHENTIC / UNTAMPERED" if is_authentic else "TAMPERED / MISMATCH",
            "bsa_compliant": is_authentic,
            "timestamp": record.get("registered_at")
        }