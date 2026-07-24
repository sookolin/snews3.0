"""Source management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.app.deps import ClientMeta, DBSession, require_permission
from shared.enums import Permission
from shared.models.city import City
from shared.models.source import Source
from shared.models.user import User
from shared.schemas.common import Message, Page, PaginationParams
from shared.schemas.source import SourceCreate, SourceOut, SourceUpdate
from shared.services.audit_service import AuditService
from shared.services.crud import CRUDService

router = APIRouter()


async def _attach_cities(session: DBSession, source: Source, city_ids: list[int]) -> None:
    cities = (
        (await session.scalars(select(City).where(City.id.in_(city_ids)))).all() if city_ids else []
    )
    source.cities = list(cities)


@router.get("", response_model=Page[SourceOut])
async def list_sources(
    session: DBSession,
    params: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> Page[SourceOut]:
    sources, total = await CRUDService(session, Source).list(params.offset, params.size)
    return Page.create([SourceOut.model_validate(s) for s in sources], total, params)


@router.post("", response_model=SourceOut, status_code=201)
async def create_source(
    payload: SourceCreate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.SOURCE_MANAGE)),
) -> SourceOut:
    data = payload.model_dump(exclude={"city_ids"})
    source = Source(**data)
    session.add(source)
    await session.flush()
    await _attach_cities(session, source, payload.city_ids)
    await session.flush()
    await AuditService(session).log(
        "source.create",
        user_id=actor.id,
        actor=actor.email,
        entity_type="source",
        entity_id=source.id,
        **meta,
    )
    return SourceOut.model_validate(source)


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> SourceOut:
    source = await CRUDService(session, Source).get_or_404(source_id)
    return SourceOut.model_validate(source)


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.SOURCE_MANAGE)),
) -> SourceOut:
    service = CRUDService(session, Source)
    source = await service.get_or_404(source_id)
    data = payload.model_dump(exclude_unset=True)
    city_ids = data.pop("city_ids", None)
    for key, value in data.items():
        setattr(source, key, value)
    if city_ids is not None:
        await _attach_cities(session, source, city_ids)
    await session.flush()
    await AuditService(session).log(
        "source.update",
        user_id=actor.id,
        actor=actor.email,
        entity_type="source",
        entity_id=source_id,
        changes=data,
        **meta,
    )
    return SourceOut.model_validate(source)


@router.delete("/{source_id}", response_model=Message)
async def delete_source(
    source_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.SOURCE_MANAGE)),
) -> Message:
    await CRUDService(session, Source).delete(source_id)
    await AuditService(session).log(
        "source.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="source",
        entity_id=source_id,
        **meta,
    )
    return Message(detail="Source deleted")


@router.post("/{source_id}/check", response_model=Message)
async def check_source_now(
    source_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.SOURCE_MANAGE)),
) -> Message:
    """Trigger an immediate ingestion run for a source via the worker queue."""
    await CRUDService(session, Source).get_or_404(source_id)
    from workers.tasks import ingest_source

    ingest_source.delay(source_id)
    return Message(detail="Source check enqueued")
