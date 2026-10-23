"""目录域业务规则：什么数据可以对外展示。

只展示已核实（confirmed_at 非空）且已发布的价格；平台未发布时其价格一并隐藏。
"""

from decimal import Decimal

from app.core.errors import AppError
from app.domains.catalog.models import (
    AIModel,
    Currency,
    ModelPrice,
    PlatformCategory,
    PublishStatus,
)
from app.domains.catalog.repository import CatalogRepository
from app.domains.catalog.schemas import (
    ModelDetail,
    ModelSummary,
    PlatformOut,
    PlatformRef,
    PriceOut,
)


def _is_public(price: ModelPrice) -> bool:
    return (
        price.status == PublishStatus.ACTIVE
        and price.confirmed_at is not None
        and price.platform.status == PublishStatus.ACTIVE
    )


def _price_out(price: ModelPrice) -> PriceOut:
    if price.confirmed_at is None:
        raise ValueError("未核实的价格不能对外输出")  # _is_public 已过滤，正常不会走到
    return PriceOut(
        platform=PlatformRef.model_validate(price.platform),
        currency=price.currency,
        input_price=price.input_price,
        output_price=price.output_price,
        cache_read_price=price.cache_read_price,
        is_free=price.is_free,
        free_note=price.free_note,
        source_url=price.source_url,
        confirmed_at=price.confirmed_at,
    )


def _public_prices(model: AIModel) -> list[ModelPrice]:
    return [p for p in model.prices if _is_public(p)]


def _min_output(prices: list[ModelPrice], currency: Currency) -> Decimal | None:
    """该币种付费价里最低的输出价；免费渠道不计入（免费另有 has_free 标记）。"""
    values = [
        p.output_price
        for p in prices
        if p.currency == currency and p.output_price is not None and p.output_price > 0
    ]
    return min(values, default=None)


class CatalogService:
    def __init__(self, repo: CatalogRepository) -> None:
        self.repo = repo

    async def list_platforms(self, category: PlatformCategory | None) -> list[PlatformOut]:
        return [PlatformOut.model_validate(p) for p in await self.repo.list_platforms(category)]

    async def get_platform(self, slug: str) -> PlatformOut:
        platform = await self.repo.get_public_platform(slug)
        if platform is None:
            raise AppError("NOT_FOUND")
        return PlatformOut.model_validate(platform)

    async def list_models(self) -> list[ModelSummary]:
        summaries: list[ModelSummary] = []
        for model in await self.repo.list_models_with_prices():
            prices = _public_prices(model)
            if not prices:
                continue  # 没有已核实价格的模型不出现在列表里
            summaries.append(
                ModelSummary(
                    slug=model.slug,
                    name=model.name,
                    family=model.family,
                    context_window=model.context_window,
                    min_output_price_cny=_min_output(prices, Currency.CNY),
                    min_output_price_usd=_min_output(prices, Currency.USD),
                    has_free=any(p.is_free for p in prices),
                    price_count=len(prices),
                )
            )
        return summaries

    async def get_model(self, slug: str) -> ModelDetail:
        model = await self.repo.get_model_with_prices(slug)
        if model is None:
            raise AppError("NOT_FOUND")
        prices = sorted(
            _public_prices(model),
            key=lambda p: (not p.is_free, p.output_price is None, p.output_price or 0),
        )
        return ModelDetail(
            slug=model.slug,
            name=model.name,
            family=model.family,
            context_window=model.context_window,
            description=model.description,
            prices=[_price_out(p) for p in prices],
        )
