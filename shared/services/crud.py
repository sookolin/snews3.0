"""Generic async CRUD service for simple table-backed resources."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Base
from shared.exceptions import NotFoundError

ModelT = TypeVar("ModelT", bound=Base)


class CRUDService(Generic[ModelT]):
    """Reusable create/read/update/delete operations for an ORM model."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, obj_id: int) -> ModelT | None:
        return await self.session.get(self.model, obj_id)

    async def get_or_404(self, obj_id: int) -> ModelT:
        obj = await self.get(obj_id)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} {obj_id} not found")
        return obj

    async def list(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
        order_by: str = "id",
        order_dir: str = "desc",
    ) -> tuple[list[ModelT], int]:
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)
        for key, value in (filters or {}).items():
            column = getattr(self.model, key, None)
            if column is not None and value is not None:
                stmt = stmt.where(column == value)
                count_stmt = count_stmt.where(column == value)
        total = await self.session.scalar(count_stmt) or 0

        column = getattr(self.model, order_by, self.model.id)
        stmt = stmt.order_by(column.desc() if order_dir == "desc" else column.asc())
        rows = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        return list(rows), total

    async def create(self, data: BaseModel | dict[str, Any]) -> ModelT:
        values = data.model_dump() if isinstance(data, BaseModel) else dict(data)
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj_id: int, data: BaseModel | dict[str, Any]) -> ModelT:
        obj = await self.get_or_404(obj_id)
        values = data.model_dump(exclude_unset=True) if isinstance(data, BaseModel) else dict(data)
        for key, value in values.items():
            setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, obj_id: int) -> None:
        obj = await self.get_or_404(obj_id)
        await self.session.delete(obj)
        await self.session.flush()

    async def clear_default(self) -> None:
        """Unset ``is_default`` on all rows (for singleton-default resources)."""
        if hasattr(self.model, "is_default"):
            objs = (
                await self.session.scalars(
                    select(self.model).where(self.model.is_default.is_(True))
                )
            ).all()
            for obj in objs:
                obj.is_default = False  # type: ignore[attr-defined]
            await self.session.flush()
