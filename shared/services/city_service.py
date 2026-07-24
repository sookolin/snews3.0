"""City service — CRUD with automatic Telegram topic creation."""

from __future__ import annotations

from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.exceptions import NotFoundError
from shared.models.city import City
from shared.schemas.city import CityCreate, CityUpdate


class CityService:
    """Manage cities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, city_id: int) -> City | None:
        return await self.session.get(City, city_id)

    async def get_or_404(self, city_id: int) -> City:
        city = await self.get(city_id)
        if city is None:
            raise NotFoundError(f"City {city_id} not found")
        return city

    async def list(
        self, offset: int = 0, limit: int = 50, active_only: bool = False
    ) -> tuple[list[City], int]:
        stmt = select(City)
        count_stmt = select(func.count()).select_from(City)
        if active_only:
            stmt = stmt.where(City.is_active.is_(True))
            count_stmt = count_stmt.where(City.is_active.is_(True))
        total = await self.session.scalar(count_stmt) or 0
        rows = (
            await self.session.scalars(stmt.order_by(City.name).offset(offset).limit(limit))
        ).all()
        return list(rows), total

    async def _unique_slug(self, name: str) -> str:
        base = slugify(name) or "city"
        slug = base
        i = 2
        while await self.session.scalar(select(City.id).where(City.slug == slug)):
            slug = f"{base}-{i}"
            i += 1
        return slug

    async def create(self, payload: CityCreate) -> City:
        city = City(
            name=payload.name,
            slug=await self._unique_slug(payload.name),
            description=payload.description,
            keywords=payload.keywords,
            extra_keywords=payload.extra_keywords,
            exclude_keywords=payload.exclude_keywords,
            region=payload.region,
            country=payload.country,
            language=payload.language,
            is_active=payload.is_active,
            template_id=payload.template_id,
        )
        self.session.add(city)
        await self.session.flush()
        return city

    async def update(self, city_id: int, payload: CityUpdate) -> City:
        city = await self.get_or_404(city_id)
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] != city.name:
            city.slug = await self._unique_slug(data["name"])
        for key, value in data.items():
            setattr(city, key, value)
        await self.session.flush()
        return city

    async def delete(self, city_id: int) -> None:
        city = await self.get_or_404(city_id)
        await self.session.delete(city)
        await self.session.flush()

    async def set_topic_id(self, city_id: int, topic_id: int) -> City:
        city = await self.get_or_404(city_id)
        city.telegram_topic_id = topic_id
        await self.session.flush()
        return city
