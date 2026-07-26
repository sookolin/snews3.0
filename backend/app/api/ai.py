"""AI profile management endpoints (+ test run)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.deps import DBSession, require_permission
from shared.enums import Permission
from shared.models.ai import AIProfile
from shared.models.user import User
from shared.plugins.ai import ai_registry
from shared.schemas.ai import AIProfileCreate, AIProfileOut, AIProfileUpdate
from shared.schemas.common import Message, Page, PaginationParams
from shared.services.ai_service import AIService
from shared.services.crud import CRUDService

router = APIRouter()


class AITestRequest(BaseModel):
    title: str | None = None
    text: str
    profile_id: int | None = None


class AITestResponse(BaseModel):
    title: str
    text: str
    provider: str


@router.get("/providers", response_model=list[str])
async def list_providers(
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> list[str]:
    """List registered AI provider plugin keys."""
    return ai_registry.keys()


@router.get("", response_model=Page[AIProfileOut])
async def list_profiles(
    session: DBSession,
    params: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> Page[AIProfileOut]:
    items, total = await CRUDService(session, AIProfile).list(params.offset, params.size)
    return Page.create([AIProfileOut.from_model(a) for a in items], total, params)


@router.post("", response_model=AIProfileOut, status_code=201)
async def create_profile(
    payload: AIProfileCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> AIProfileOut:
    service = CRUDService(session, AIProfile)
    if payload.is_default:
        await service.clear_default()
    obj = await service.create(payload)
    return AIProfileOut.from_model(obj)


@router.patch("/{profile_id}", response_model=AIProfileOut)
async def update_profile(
    profile_id: int,
    payload: AIProfileUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> AIProfileOut:
    service = CRUDService(session, AIProfile)
    if payload.is_default:
        await service.clear_default()
    data = payload.model_dump(exclude_unset=True)
    # Empty api_key means "keep existing" — don't overwrite the stored secret.
    if "api_key" in data and not (data["api_key"] or "").strip():
        data.pop("api_key")
    obj = await service.update(profile_id, data)
    return AIProfileOut.from_model(obj)


@router.delete("/{profile_id}", response_model=Message)
async def delete_profile(
    profile_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> Message:
    await CRUDService(session, AIProfile).delete(profile_id)
    return Message(detail="AI profile deleted")


@router.post("/test", response_model=AITestResponse)
async def test_ai(
    payload: AITestRequest,
    session: DBSession,
    _: User = Depends(require_permission(Permission.AI_MANAGE)),
) -> AITestResponse:
    """Run an AI profile against sample text to verify configuration."""
    result, profile = await AIService(session).process(
        payload.title, payload.text, payload.profile_id
    )
    return AITestResponse(title=result.title, text=result.text, provider=profile.provider.value)
