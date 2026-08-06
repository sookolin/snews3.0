"""City management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import ClientMeta, DBSession, require_city_access, require_permission
from shared.enums import Permission
from shared.logging import get_logger
from shared.models.user import User
from shared.schemas.city import CityCreate, CityOut, CityUpdate
from shared.schemas.common import Message, Page, PaginationParams
from shared.security import user_city_access
from shared.services.audit_service import AuditService
from shared.services.city_service import CityService

router = APIRouter()
log = get_logger("api.cities")


@router.get("", response_model=Page[CityOut])
async def list_cities(
    session: DBSession,
    params: PaginationParams = Depends(),
    active_only: bool = False,
    actor: User = Depends(require_permission(Permission.CITY_VIEW)),
) -> Page[CityOut]:
    allowed = user_city_access(actor, Permission.CITY_VIEW)
    cities, total = await CityService(session).list(
        params.offset, params.size, active_only, allowed_city_ids=allowed
    )
    return Page.create([CityOut.model_validate(c) for c in cities], total, params)


@router.post("", response_model=CityOut, status_code=201)
async def create_city(
    payload: CityCreate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.CITY_MANAGE)),
) -> CityOut:
    service = CityService(session)
    city = await service.create(payload)

    await AuditService(session).log(
        "city.create",
        user_id=actor.id,
        actor=actor.email,
        entity_type="city",
        entity_id=city.id,
        **meta,
    )
    return CityOut.model_validate(city)


@router.get("/{city_id}", response_model=CityOut)
async def get_city(
    city_id: int,
    session: DBSession,
    actor: User = Depends(require_permission(Permission.CITY_VIEW)),
) -> CityOut:
    require_city_access(city_id, actor, Permission.CITY_VIEW)
    city = await CityService(session).get_or_404(city_id)
    return CityOut.model_validate(city)


@router.patch("/{city_id}", response_model=CityOut)
async def update_city(
    city_id: int,
    payload: CityUpdate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.CITY_MANAGE)),
) -> CityOut:
    require_city_access(city_id, actor, Permission.CITY_MANAGE)
    city = await CityService(session).update(city_id, payload)
    await AuditService(session).log(
        "city.update",
        user_id=actor.id,
        actor=actor.email,
        entity_type="city",
        entity_id=city_id,
        changes=payload.model_dump(exclude_unset=True),
        **meta,
    )
    return CityOut.model_validate(city)


@router.delete("/{city_id}", response_model=Message)
async def delete_city(
    city_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.CITY_MANAGE)),
) -> Message:
    require_city_access(city_id, actor, Permission.CITY_MANAGE)
    await CityService(session).delete(city_id)
    await AuditService(session).log(
        "city.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="city",
        entity_id=city_id,
        **meta,
    )
    return Message(detail="City deleted")


@router.post("/{city_id}/weather/test", response_model=Message)
async def test_weather(
    city_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CITY_MANAGE)),
) -> Message:
    """Publish the weather post for this city right now (manual check).

    Runs synchronously so the operator gets an immediate result: how many
    channels received the post, or a clear reason if none did. Bypasses the
    schedule and the once-per-day marker.
    """
    from shared.exceptions import ExternalServiceError, NotFoundError
    from workers.tasks import _publish_weather_for_city

    city = await CityService(session).get_or_404(city_id)
    if city is None:
        raise NotFoundError("Город не найден")
    try:
        sent = await _publish_weather_for_city(session, city)
    except Exception as exc:  # noqa: BLE001
        raise ExternalServiceError(f"Не удалось опубликовать погоду: {exc}") from exc
    await session.commit()
    if sent == 0:
        raise ExternalServiceError(
            "Погода не опубликована: нет активных каналов у города, "
            "либо не удалось получить прогноз/координаты."
        )
    return Message(detail=f"Погода опубликована в каналов: {sent}")
