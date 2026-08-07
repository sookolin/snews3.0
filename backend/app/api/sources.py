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
from shared.security import user_city_access
from shared.services.audit_service import AuditService
from shared.services.crud import CRUDService

router = APIRouter()


def _check_source_city_access(source: Source, actor: User, permission: Permission) -> None:
    """Enforce city-scoped RBAC for a single source: the actor must have
    access to at least one of the source's linked cities, or the source has
    no city link at all (global sources aren't gated by city).
    """
    from shared.exceptions import PermissionDeniedError

    allowed = user_city_access(actor, permission)
    if allowed is None:
        return
    linked = [c.id for c in (source.cities or [])]
    if linked and not any(cid in allowed for cid in linked):
        raise PermissionDeniedError("Нет доступа к этому источнику", code="city_access_denied")


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
    actor: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> Page[SourceOut]:
    from sqlalchemy import func, or_
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

    # City-scoped SOURCE_VIEW: only show sources linked to an allowed city,
    # or with no city link at all (global sources aren't tied to any city).
    allowed = user_city_access(actor, Permission.SOURCE_VIEW)
    if allowed is not None:
        allowed_stmt = select(source_cities.c.source_id).where(source_cities.c.city_id.in_(allowed))
        scope = or_(
            Source.id.in_(allowed_stmt),
            ~Source.id.in_(select(source_cities.c.source_id)),
        )
        stmt = stmt.where(scope)
        count_stmt = count_stmt.where(scope)

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
    actor: User = Depends(require_permission(Permission.SOURCE_VIEW)),
) -> SourceOut:
    source = await session.scalar(
        select(Source).options(selectinload(Source.cities)).where(Source.id == source_id)
    )
    if source is None:
        from shared.exceptions import NotFoundError

        raise NotFoundError(f"Source {source_id} not found")
    _check_source_city_access(source, actor, Permission.SOURCE_VIEW)
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
    await session.refresh(source, attribute_names=["cities"])
    _check_source_city_access(source, actor, Permission.SOURCE_MANAGE)
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
    service = CRUDService(session, Source)
    source = await service.get_or_404(source_id)
    await session.refresh(source, attribute_names=["cities"])
    _check_source_city_access(source, actor, Permission.SOURCE_MANAGE)
    await service.delete(source_id)
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
