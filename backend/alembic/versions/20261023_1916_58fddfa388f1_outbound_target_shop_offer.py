"""outbound target shop offer

Revision ID: 58fddfa388f1
Revises: 28e906e01d62
Create Date: 2026-10-23 19:16:55.106618

出站点击新增跳转对象类型 shop_offer（卡网报价）。枚举存为 VARCHAR + CHECK 约束，
autogenerate 识别不到约束取值的变化，手写：重建约束。
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "58fddfa388f1"
down_revision: str | Sequence[str] | None = "28e906e01d62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "outbound_clicks"
# op.f：已是最终名称，不再套命名约定（否则会变成 ck_outbound_clicks_ck_outbound_clicks_…）
NAME = op.f("ck_outbound_clicks_outboundtarget")


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(NAME, TABLE, type_="check")
    op.create_check_constraint(NAME, TABLE, "target_type IN ('deal', 'shop_offer')")


def downgrade() -> None:
    """Downgrade schema."""
    # 回滚前先删掉卡网报价的点击记录，否则旧约束建不起来
    op.execute("DELETE FROM outbound_clicks WHERE target_type = 'shop_offer'")
    op.drop_constraint(NAME, TABLE, type_="check")
    op.create_check_constraint(NAME, TABLE, "target_type IN ('deal')")
