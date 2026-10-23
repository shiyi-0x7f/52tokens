"""价格后台：手工录入 / 更新官方 API 价格（OpenRouter 不覆盖的国内官方平台等）。

手工录入即视为当场从官网核实：保存时写入 confirmed_at 并发布。
模型不存在时按填写的名称和系列新建。
"""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.core.errors import AppError
from app.domains.catalog.models import (
    AIModel,
    Currency,
    ModelPrice,
    PlatformCategory,
    PublishStatus,
)
from app.domains.catalog.repository import CatalogRepository
from app.domains.common import Page, PageQuery

MODEL_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,78}[a-z0-9]$"
PRICE_FIELD = Field(default=None, ge=0, max_digits=12, decimal_places=4)


class PlatformAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    category: PlatformCategory
    status: PublishStatus


class ModelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    family: str


class PriceIn(BaseModel):
    platform_id: int
    model_slug: str = Field(pattern=MODEL_SLUG_PATTERN)
    # 模型不存在时用于新建；已存在时忽略
    model_name: str | None = Field(default=None, max_length=120)
    family: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,40}$")
    context_window: int | None = Field(default=None, gt=0)
    currency: Currency = Currency.CNY
    input_price: Decimal | None = PRICE_FIELD
    output_price: Decimal | None = PRICE_FIELD
    cache_read_price: Decimal | None = PRICE_FIELD
    is_free: bool = False
    free_note: str = Field(default="", max_length=200)
    source_url: HttpUrl

    @model_validator(mode="after")
    def _has_price(self) -> "PriceIn":
        if not self.is_free and (self.input_price is None or self.output_price is None):
            raise ValueError("非免费价格必须填写输入价和输出价")
        return self


class PriceAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: PlatformAdminOut
    model: ModelBrief
    currency: Currency
    input_price: Decimal | None
    output_price: Decimal | None
    cache_read_price: Decimal | None
    is_free: bool
    free_note: str
    source_url: str
    confirmed_at: datetime | None
    status: PublishStatus
    updated_at: datetime


class PriceListQuery(PageQuery):
    platform_id: int | None = None
    q: str | None = Field(default=None, max_length=50)


class PriceAdminService:
    def __init__(self, repo: CatalogRepository) -> None:
        self.repo = repo

    async def platforms(self) -> list[PlatformAdminOut]:
        return [PlatformAdminOut.model_validate(p) for p in await self.repo.list_all_platforms()]

    async def list(self, query: PriceListQuery) -> Page[PriceAdminOut]:
        rows, total = await self.repo.list_prices(
            platform_id=query.platform_id, q=query.q, offset=query.offset, limit=query.page_size
        )
        return Page(
            items=[PriceAdminOut.model_validate(p) for p in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def _out(self, price_id: int) -> PriceAdminOut:
        price = await self.repo.get_price(price_id)
        if price is None:
            raise AppError("NOT_FOUND", "价格不存在")
        return PriceAdminOut.model_validate(price)

    async def _model(self, data: PriceIn) -> AIModel:
        model = await self.repo.get_model_by_slug(data.model_slug)
        if model is not None:
            if data.context_window and not model.context_window:
                model.context_window = data.context_window
            return model
        if not data.model_name or not data.family:
            raise AppError("BAD_REQUEST", "新模型需要填写模型名称和系列")
        model = AIModel(
            slug=data.model_slug,
            name=data.model_name.strip(),
            family=data.family,
            context_window=data.context_window,
            description="",
            status=PublishStatus.ACTIVE,
        )
        self.repo.add(model)
        await self.repo.flush()
        return model

    async def save(self, data: PriceIn) -> PriceAdminOut:
        """按（平台, 模型）新建或更新价格，保存即视为已核实并发布。"""
        if await self.repo.get_platform(data.platform_id) is None:
            raise AppError("BAD_REQUEST", "平台不存在")
        model = await self._model(data)
        price = await self.repo.get_price_for(data.platform_id, model.id)
        if price is None:
            price = ModelPrice(platform_id=data.platform_id, model_id=model.id)
            self.repo.add(price)
        price.currency = data.currency
        price.input_price = data.input_price
        price.output_price = data.output_price
        price.cache_read_price = data.cache_read_price
        price.is_free = data.is_free
        price.free_note = data.free_note.strip()
        price.source_url = str(data.source_url)
        price.confirmed_at = datetime.now(UTC)
        price.status = PublishStatus.ACTIVE
        await self.repo.flush()
        price_id = price.id
        await self.repo.commit()
        return await self._out(price_id)

    async def set_status(self, price_id: int, status: PublishStatus) -> PriceAdminOut:
        price = await self.repo.get_price(price_id)
        if price is None:
            raise AppError("NOT_FOUND", "价格不存在")
        price.status = status
        await self.repo.commit()
        return await self._out(price_id)
