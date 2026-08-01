"""Source management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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


async def _set_source_cities(session: DBSession, source_id: int, city_ids: list[int]) -> None:
    """Replace a source's city links via the association table (no lazy load)."""
    from sqlalchemy import delete, insert

    from shared.models.source import source_cities

    await session.execute(delete(source_cities).where(source_cities.c.source_id == source_id))
    if city_ids:
        # Keep only existing cities to satisfy FK.
        valid = (await session.scalars(select(City.id).where(City.id.in_(city_ids)))).all()
        if valid:
            await session.execute(
                insert(source_cities),
                [{"source_id": source_id, "city_id": cid} for cid in valid],
            )


@router.get("", response_model=Page[SourceOut])
async def list_sources(
    session: DBSession,
    params: PaginationParams = Depends(),
    city_id: int | None = None,
    _: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> Page[SourceOut]:
    from sqlalchemy import func
    from sqlalchemy.orm import selectinload
    from shared.models.source import source_cities

    stmt = select(Source).options(selectinload(Source.cities))
    count_stmt = select(func.count()).select_from(Source)

    if city_id is not None:
        stmt = stmt.join(source_cities, source_cities.c.source_id == Source.id).where(
            source_cities.c.city_id == city_id
        )
        count_stmt = count_stmt.join(source_cities, source_cities.c.source_id == Source.id).where(
            source_cities.c.city_id == city_id
        )

    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.scalars(stmt.order_by(Source.id.desc()).offset(params.offset).limit(params.size))
    ).all()
    return Page.create([SourceOut.model_validate(s) for s in rows], total, params)


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
    await _set_source_cities(session, source.id, payload.city_ids)
    await AuditService(session).log(
        "source.create",
        user_id=actor.id,
        actor=actor.email,
        entity_type="source",
        entity_id=source.id,
        **meta,
    )
    await session.commit()
    # Re-fetch with the relationship eagerly loaded for safe serialization.
    fresh = await session.scalar(
        select(Source).options(selectinload(Source.cities)).where(Source.id == source.id)
    )
    return SourceOut.model_validate(fresh)


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> SourceOut:
    source = await session.scalar(
        select(Source).options(selectinload(Source.cities)).where(Source.id == source_id)
    )
    if source is None:
        from shared.exceptions import NotFoundError

        raise NotFoundError(f"Source {source_id} not found")
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
    await session.flush()
    if city_ids is not None:
        await _set_source_cities(session, source_id, city_ids)
    await AuditService(session).log(
        "source.update",
        user_id=actor.id,
        actor=actor.email,
        entity_type="source",
        entity_id=source_id,
        changes=data,
        **meta,
    )
    await session.commit()
    fresh = await session.scalar(
        select(Source).options(selectinload(Source.cities)).where(Source.id == source_id)
    )
    return SourceOut.model_validate(fresh)


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
