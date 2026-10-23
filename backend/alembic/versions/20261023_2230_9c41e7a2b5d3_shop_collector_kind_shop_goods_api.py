"""shop collector kind shopGoodsApi

Revision ID: 9c41e7a2b5d3
Revises: 58fddfa388f1
Create Date: 2026-10-23 22:30:00.000000

卡网店铺系统新增 shopGoodsApi（16688 等多商户平台）。枚举存为 VARCHAR + CHECK 约束，
autogenerate 识别不到约束取值的变化，手写：重建约束。
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c41e7a2b5d3"
down_revision: str | Sequence[str] | None = "58fddfa388f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "shop_sources"
# op.f：已是最终名称，不再套命名约定
NAME = op.f("ck_shop_sources_shopcollectorkind")
_OLD = (
    "kami",
    "dujiao",
    "shopApi",
    "xiaoheiwan",
    "opensoraHtml",
    "makerichHtml",
    "beibeiHtml",
    "ikunloveApi",
    "getgptApi",
    "publicProductsApi",
    "shopUserProductsApi",
    "unicornHtml",
    "mooncakeCatalog",
    "blackcatWholesale",
    "genericHtml",
)
_NEW = (*_OLD, "shopGoodsApi")


def _check(values: tuple[str, ...]) -> str:
    return "collector_kind IN ({})".format(", ".join(f"'{v}'" for v in values))


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(NAME, TABLE, type_="check")
    op.create_check_constraint(NAME, TABLE, _check(_NEW))


def downgrade() -> None:
    """Downgrade schema."""
    # 回滚前先删掉这类店铺（报价随外键级联删除），否则旧约束建不起来
    op.execute("DELETE FROM shop_sources WHERE collector_kind = 'shopGoodsApi'")
    op.drop_constraint(NAME, TABLE, type_="check")
    op.create_check_constraint(NAME, TABLE, _check(_OLD))
