"""卡网比价（公开站服务端专用）。"""

from fastapi import APIRouter

from app.api.deps import ShopServiceDep
from app.core.response import ApiResponse, ok
from app.domains.shops.schemas import ShopProductDetail, ShopProductSummary

router = APIRouter(tags=["internal:shops"])


@router.get("/shop-products")
async def list_shop_products(service: ShopServiceDep) -> ApiResponse[list[ShopProductSummary]]:
    return ok(await service.list_products())


@router.get("/shop-products/{slug}")
async def get_shop_product(slug: str, service: ShopServiceDep) -> ApiResponse[ShopProductDetail]:
    return ok(await service.get_product(slug))
