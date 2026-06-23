import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List

from backend.agents.discovery_agent import DiscoveryAgent
from backend.auth.dependencies import get_current_user
from backend.db.models import User

router = APIRouter()

# ── Pydantic Request Models ───────────────────────────────────────────────────

class PreviewSpecUrl(BaseModel):
    spec_url: str

class ManualEndpointInput(BaseModel):
    path: str
    method: str
    description: str = ""
    payload: Optional[dict] = None

class PreviewManual(BaseModel):
    endpoints: List[ManualEndpointInput]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/preview/spec-url")
async def preview_spec_url(
    body: PreviewSpecUrl,
    user: User = Depends(get_current_user),
):
    """Parse and preview endpoints from an OpenAPI spec URL."""
    discovery = DiscoveryAgent()
    try:
        preview_data = await discovery.preview_from_openapi_url(body.spec_url)
        return preview_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview/spec-file")
async def preview_spec_file(
    spec_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Parse and preview endpoints from an uploaded OpenAPI spec file."""
    content = await spec_file.read()
    content_str = content.decode("utf-8")
    
    discovery = DiscoveryAgent()
    try:
        preview_data = await discovery.preview_from_openapi_content(content_str)
        return preview_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview/postman")
async def preview_postman(
    collection_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Parse and preview endpoints from an uploaded Postman Collection JSON."""
    content = await collection_file.read()
    try:
        collection_data = json.loads(content.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON. Export as Collection v2.1 from Postman."
        )
        
    discovery = DiscoveryAgent()
    try:
        preview_data = await discovery.preview_from_postman(collection_data)
        return preview_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview/manual")
async def preview_manual(
    body: PreviewManual,
    user: User = Depends(get_current_user),
):
    """Preview manually entered endpoints grouped under the 'Manual' tag."""
    if not body.endpoints:
        raise HTTPException(status_code=400, detail="No endpoints provided.")
        
    discovery = DiscoveryAgent()
    endpoints_raw = []
    for ep in body.endpoints:
        endpoints_raw.append({
            "path": ep.path,
            "method": ep.method,
            "description": ep.description,
            "payload": ep.payload
        })
        
    try:
        preview_data = await discovery.preview_from_manual(endpoints_raw)
        return preview_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
