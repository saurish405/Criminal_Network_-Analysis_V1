import os
import uuid
import re
from typing import Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.api.auth import SECRET_KEY, ALGORITHM
from app.api.schemas import EvidenceVerifyResponse
from app.services.document_parser import DocumentParserService
from app.services.nlp_extractor import NLPExtractorService
from app.services.graph_engine import GraphEngineService
from app.services.evidence_vault import EvidenceVaultService
from app.services.osint_service import OSINTService

router = APIRouter()

nlp_service = NLPExtractorService()
graph_service = GraphEngineService()

cached_graph_state: dict = {
    "nodes": [],
    "links": [],
    "stats": {
        "total_entities": 0,
        "total_connections": 0,
        "detected_syndicates": 0,
        "critical_threat_nodes": 0
    },
    "case_timeline": []
}

# --- 1. SECURITY & AUTHENTICATION GUARD ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

async def get_current_officer(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Validates the JWT token issued by auth.py.
    Provides a default officer identity during local testing if no Bearer token is passed.
    """
    if not token:
        return {"username": "officer@ncrb.gov.in", "role": "Lead Investigating Officer (IO)"}

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"username": username, "role": payload.get("role")}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or cryptographic signature mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- 2. ASYNCHRONOUS OSINT & GOVT DATABASE ENRICHMENT WORKER ---
async def run_osint_enrichment_task(graph_data: dict):
    """
    Asynchronously queries OSINT and live/mock government gateways (Vahan, Telecom, CCTNS)
    to enrich node intelligence without blocking document ingestion response.
    """
    for node in graph_data.get("nodes", []):
        ntype = node.get("type")
        val = str(node.get("name", ""))
        details = node.setdefault("details", {})

        try:
            if ntype == "PHONE":
                telecom_info = await OSINTService.get_telecom_circle(val)
                details.update(telecom_info)

            elif ntype == "VEHICLE":
                vehicle_info = await OSINTService.get_vehicle_rto(val)
                details.update(vehicle_info)

            elif ntype == "PERSON":
                # Check national criminal dossiers (CCTNS / ICJS)
                cctns_info = await OSINTService.get_cctns_record(val)
                details["cctns_intel"] = cctns_info

            elif ntype == "BANK_ACCOUNT":
                acc_num = details.get("account_full", val)
                if acc_num.startswith("1"):
                    bank = "HDFC Bank Ltd"
                elif acc_num.startswith(("2", "3")):
                    bank = "ICICI Bank Ltd"
                elif acc_num.startswith(("0", "9")):
                    bank = "Punjab National Bank"
                else:
                    bank = "State Bank of India"
                details["osint_clearing_bank"] = bank
                details["osint_freeze_eligible"] = True
        except Exception:
            continue


# --- 3. CORE INGESTION ROUTE ---
@router.post("/ingest/fir")
async def ingest_fir(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_officer: dict = Depends(get_current_officer)
):
    global cached_graph_state

    valid_exts = (".pdf", ".docx", ".doc", ".txt")
    if not file.filename.lower().endswith(valid_exts):
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Only PDF, DOCX, and TXT files are permitted."
        )

    try:
        content = await file.read()

        # Binary magic-byte header validation
        if file.filename.lower().endswith(".pdf") and not content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Corrupt or invalid PDF file header.")
        if file.filename.lower().endswith((".docx", ".doc")) and not content.startswith(b"PK\x03\x04"):
            raise HTTPException(status_code=400, detail="Corrupt or invalid DOCX archive header.")

        # Text extraction and SHA-3 (256-bit) cryptographic digest
        extracted_text, doc_sha3 = DocumentParserService.extract_text(content, file.filename)

        if not extracted_text:
            raise HTTPException(
                status_code=422,
                detail="Unable to parse text from document. Ensure file is not empty or password protected."
            )

        # Register document block in the SHA-3 blockchain ledger
        doc_id = f"DOC_{uuid.uuid4().hex[:8].upper()}"
        EvidenceVaultService.register_document(
            doc_id=doc_id,
            sha3_hash=doc_sha3,
            filename=file.filename,
            file_bytes=content,
            officer_id=current_officer.get("username", "POLICE_NCRB_OFFICER_01")
        )

        # Entity, item context, and chronological incident date extraction
        structured_entities = nlp_service.extract_structured_regex(extracted_text)
        named_entities = nlp_service.extract_named_entities(extracted_text)
        case_timeline = nlp_service.extract_case_dates(extracted_text)

        # Construct nodes and relationship links
        raw_nodes, raw_links = nlp_service.build_network_triplets(
            text=extracted_text,
            structured=structured_entities,
            named=named_entities
        )

        graph_service.construct_graph(raw_nodes, raw_links)
        analytics_result = graph_service.analyze_and_score()
        analytics_result["case_timeline"] = case_timeline

        # Dispatch background OSINT & Govt DB lookup
        background_tasks.add_task(run_osint_enrichment_task, analytics_result)

        cached_graph_state = analytics_result
        return analytics_result

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion processing error: {str(e)}")


# --- 4. ON-DEMAND GOVERNMENT DATABASE & OSINT QUERY PROXY ---
@router.get("/osint/query")
async def query_government_osint(
    entity_type: str,
    value: str,
    current_officer: dict = Depends(get_current_officer)
):
    """
    On-demand proxy route to query external government databases for an entity.
    entity_type options: 'PHONE', 'VEHICLE', or 'PERSON'
    """
    etype = entity_type.upper()
    if etype == "PHONE":
        return await OSINTService.get_telecom_circle(value)
    elif etype == "VEHICLE":
        return await OSINTService.get_vehicle_rto(value)
    elif etype == "PERSON":
        return await OSINTService.get_cctns_record(value)
    else:
        raise HTTPException(status_code=400, detail="Invalid entity type. Permitted: PHONE, VEHICLE, PERSON.")


# --- 5. GRAPH DATA & BLOCKCHAIN AUDIT ROUTES ---
@router.get("/graph/data")
async def get_graph_data(current_officer: dict = Depends(get_current_officer)):
    return cached_graph_state


@router.get("/evidence/blockchain-ledger")
async def get_evidence_blockchain_ledger(current_officer: dict = Depends(get_current_officer)):
    return EvidenceVaultService.get_blockchain_ledger()


@router.get("/evidence/audit-log")
async def get_evidence_audit_log(current_officer: dict = Depends(get_current_officer)):
    return EvidenceVaultService.get_all_records()


@router.get("/evidence/download/{filename}")
async def download_evidence(filename: str, current_officer: dict = Depends(get_current_officer)):
    path = os.path.join("evidence_store", filename)
    if os.path.exists(path):
        return FileResponse(path, filename=filename)
    raise HTTPException(status_code=404, detail="Requested evidentiary file not found on disk.")


@router.post("/evidence/verify", response_model=EvidenceVerifyResponse)
async def verify_document_integrity(
    doc_id: str,
    file: UploadFile = File(...),
    current_officer: dict = Depends(get_current_officer)
):
    try:
        content = await file.read()
        return EvidenceVaultService.verify_document(doc_id, content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")