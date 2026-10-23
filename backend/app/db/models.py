"""汇总导入所有 ORM 模型，供 Alembic autogenerate 和测试建表使用。新增业务域时在这里加一行。"""

from app.domains.accounts import models as accounts_models
from app.domains.catalog import models as catalog_models
from app.domains.deals import models as deals_models
from app.domains.official import models as official_models
from app.domains.outbound import models as outbound_models
from app.domains.shops import models as shops_models

__all__ = [
    "accounts_models",
    "catalog_models",
    "deals_models",
    "official_models",
    "outbound_models",
    "shops_models",
]
