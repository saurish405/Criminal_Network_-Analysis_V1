from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class GraphNode(BaseModel):
    id: str
    name: str
    type: str  # SUSPECT, PHONE, BANK_ACCOUNT, VEHICLE, LOCATION
    risk_score: float = Field(..., ge=0.0, le=1.0)
    color: str
    size: int
    cluster: str
    details: Dict[str, Any] = Field(default_factory=dict)

class GraphLink(BaseModel):
    source: str
    target: str
    relationship: str
    label: str
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None

class NetworkStats(BaseModel):
    total_entities: int
    total_connections: int
    detected_syndicates: int
    critical_threat_nodes: int

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]
    stats: NetworkStats

class EvidenceRecord(BaseModel):
    document_id: str
    filename: str
    sha256_hash: str
    registered_at: str
    officer_id: str
    bsa_section_63_verified: bool
    tamper_detected: bool

class EvidenceVerifyResponse(BaseModel):
    document_id: str
    sha256_hash: str
    original_hash: Optional[str] = None
    tamper_status: str
    bsa_compliant: bool
    timestamp: Optional[str] = None