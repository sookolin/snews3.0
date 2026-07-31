"""Template management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import DBSession, require_permission
from shared.enums import Permission
from shared.models.template import Template
from shared.models.user import User
from shared.schemas.common import Message, Page, PaginationParams
from shared.schemas.template import TemplateCreate, TemplateOut, TemplateUpdate
from shared.services.crud import CRUDService

router = APIRouter()


@router.get("", response_model=Page[TemplateOut])
async def list_templates(
    session: DBSession,
    params: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> Page[TemplateOut]:
    items, total = await CRUDService(session, Template).list(params.offset, params.size)
    return Page.create([TemplateOut.model_validate(t) for t in items], total, params)


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    payload: TemplateCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> TemplateOut:
    service = CRUDService(session, Template)
    if payload.is_default:
        await service.clear_default()
    obj = await service.create(payload)
    return TemplateOut.model_validate(obj)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> TemplateOut:
    obj = await CRUDService(session, Template).get_or_404(template_id)
    return TemplateOut.model_validate(obj)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    payload: TemplateUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> TemplateOut:
    service = CRUDService(session, Template)
    if payload.is_default:
        await service.clear_default()
    obj = await service.update(template_id, payload)
    return TemplateOut.model_validate(obj)


@router.delete("/{template_id}", response_model=Message)
async def delete_template(
    template_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> Message:
    await CRUDService(session, Template).delete(template_id)
    return Message(detail="Template deleted")


@router.post("/{template_id}/duplicate", response_model=TemplateOut, status_code=201)
async def duplicate_template(
    template_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> TemplateOut:
    """Create a copy of a template (never inherits the "default" flag)."""
    source = await CRUDService(session, Template).get_or_404(template_id)
    copy = Template(
        name=f"{source.name} (копия)"[:255],
        is_default=False,
        is_active=source.is_active,
        format=source.format,
        header=source.header,
        body=source.body,
        footer=source.footer,
        separator=source.separator,
        subscribe_link=source.subscribe_link,
        variables=dict(source.variables or {}),
        disable_web_preview=source.disable_web_preview,
        uppercase_title=source.uppercase_title,
    )
    session.add(copy)
    await session.flush()
    await session.refresh(copy)
    return TemplateOut.model_validate(copy)


@router.post("/{template_id}/preview", response_model=Message)
async def preview_template(
    template_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
) -> Message:
    """Render the template with sample data for a live preview."""
    import json as _json
    from shared.services.template_renderer import TemplateRenderer
    from shared.services.settings_service import SettingsService

    template = await CRUDService(session, Template).get_or_404(template_id)

    # Load global tags so the preview reflects what will actually be published.
    global_tags: list[dict] = []
    try:
        raw = await SettingsService(session).get("templates.global_tags", "") or ""
        if isinstance(raw, str) and raw.strip().startswith("["):
            global_tags = _json.loads(raw)
        elif isinstance(raw, list):
            global_tags = raw
    except Exception:
        pass

    rendered = TemplateRenderer().render(
        template,
        title="Пример заголовка новости",
        text="Это пример текста новости для предпросмотра шаблона.",
        source="Пример источника",
        source_url="https://example.com",
        city="Пример города",
        author="Иван Иванов",
        emoji="🔥",
        global_tags=global_tags,
    )
    return Message(detail=rendered)
