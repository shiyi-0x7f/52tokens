from fastapi import APIRouter

from app.api.deps import AdminDep
from app.core.response import ApiResponse, ok
from app.domains.accounts.schemas import UserOut

router = APIRouter(tags=["admin"])


@router.get("/me")
async def me(user: AdminDep) -> ApiResponse[UserOut]:
    return ok(user)
