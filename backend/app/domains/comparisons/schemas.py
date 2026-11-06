"""精选模型对比的出入参。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.catalog.admin import MODEL_SLUG_PATTERN, ModelBrief
from app.domains.catalog.models import PublishStatus
from app.domains.common import PageQuery


class ModelRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    family: str


class ComparisonOut(BaseModel):
    """对外：顺序即网址顺序 /models/{a}-vs-{b}。"""

    model_config = ConfigDict(from_attributes=True)

    model_a: ModelRef
    model_b: ModelRef
    intro: str
    updated_at: datetime


class ComparisonAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_a: ModelBrief
    model_b: ModelBrief
    intro: str
    sort_order: int
    status: PublishStatus
    updated_at: datetime


class ComparisonUpdate(BaseModel):
    intro: str = Field(default="", max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=9999)


class ComparisonIn(ComparisonUpdate):
    model_a_slug: str = Field(pattern=MODEL_SLUG_PATTERN)
    model_b_slug: str = Field(pattern=MODEL_SLUG_PATTERN)

    @model_validator(mode="after")
    def _distinct(self) -> "ComparisonIn":
        if self.model_a_slug == self.model_b_slug:
            raise ValueError("对比的两个模型不能相同")
        return self


class ComparisonListQuery(PageQuery):
    q: str | None = Field(default=None, max_length=50)


class ModelSearchQuery(BaseModel):
    q: str | None = Field(default=None, max_length=50)
