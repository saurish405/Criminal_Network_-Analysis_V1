import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from app.api.schemas import GraphResponse, EvidenceRecord, EvidenceVerifyResponse
from app.services.document_parser import DocumentParserService
from app.services.nlp_extractor import NLPExtractorService
from app.services.graph_engine import GraphEngineService
from app.services.evidence_vault import EvidenceVaultService

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
    }
}

@router.post("/ingest/fir", response_model=GraphResponse)
async def ingest_fir(file: UploadFile = File(...)):
    global cached_graph_state
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        content = await file.read()
        
        extracted_text, doc_sha256 = DocumentParserService.extract_text_from_pdf(content)
        
        if not extracted_text:
            raise HTTPException(
                status_code=422, 
                detail="Unable to extract text. The document may be empty or unreadable."
            )

        doc_id = f"DOC_{uuid.uuid4().hex[:8].upper()}"
        EvidenceVaultService.register_document(
            doc_id=doc_id,
            sha256_hash=doc_sha256,
            filename=file.filename
        )

        structured_entities = nlp_service.extract_structured_regex(extracted_text)
        named_entities = nlp_service.extract_named_entities(extracted_text)

        raw_nodes, raw_links = nlp_service.build_network_triplets(
            text=extracted_text,
            structured=structured_entities,
            named=named_entities
        )

        graph_service.construct_graph(raw_nodes, raw_links)
        analytics_result = graph_service.analyze_and_score()

        cached_graph_state = analytics_result
        return analytics_result

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion processing error: {str(e)}")

@router.get("/graph/data", response_model=GraphResponse)
async def get_graph_data():
    return cached_graph_state

@router.get("/evidence/audit-log")
async def get_evidence_audit_log():
    return EvidenceVaultService.get_all_records()

@router.post("/evidence/verify", response_model=EvidenceVerifyResponse)
async def verify_document_integrity(
    doc_id: str, 
    file: UploadFile = File(...)
):
    try:
        content = await file.read()
        verification_result = EvidenceVaultService.verify_document(doc_id, content)
        return verification_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")