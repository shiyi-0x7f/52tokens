"""精选模型对比：后台维护名单、对外只给已发布的组合、两个模型不分先后。"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.catalog.models import PublishStatus
from tests import factories as f
from tests.conftest import AUTH, CSRF

BASE = "/api/admin/model-comparisons"


async def _models(session: AsyncSession) -> None:
    await f.model(session, "deepseek-v3-2", name="DeepSeek V3.2")
    await f.model(session, "qwen3-max", name="Qwen3 Max")
    await f.model(session, "glm-4-6", name="GLM-4.6")
    await f.model(session, "old-model", status=PublishStatus.DRAFT)
    await session.commit()


async def _create(admin: httpx.AsyncClient, a: str, b: str, **kw: object) -> httpx.Response:
    return await admin.post(BASE, json={"model_a_slug": a, "model_b_slug": b, **kw}, headers=CSRF)


async def test_admin_create_rejects_duplicates_in_either_order(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    await _models(db_session)
    resp = await _create(admin, "deepseek-v3-2", "qwen3-max", intro=" 选型建议 ")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert (data["model_a"]["slug"], data["model_b"]["slug"]) == ("deepseek-v3-2", "qwen3-max")
    assert data["intro"] == "选型建议"

    again = await _create(admin, "qwen3-max", "deepseek-v3-2")  # 反过来也算重复
    assert again.status_code == 409

    assert (await _create(admin, "deepseek-v3-2", "deepseek-v3-2")).status_code == 422
    assert (await _create(admin, "deepseek-v3-2", "nope-model")).status_code == 400


async def test_admin_update_hide_and_delete(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    await _models(db_session)
    cid = (await _create(admin, "deepseek-v3-2", "glm-4-6")).json()["data"]["id"]

    upd = await admin.put(f"{BASE}/{cid}", json={"intro": "新导语", "sort_order": 5}, headers=CSRF)
    assert upd.json()["data"]["intro"] == "新导语"
    assert upd.json()["data"]["sort_order"] == 5

    hidden = await admin.post(f"{BASE}/{cid}/hide", headers=CSRF)
    assert hidden.json()["data"]["status"] == "hidden"

    listed = (await admin.get(BASE, params={"q": "glm"})).json()["data"]
    assert listed["total"] == 1

    assert (await admin.delete(f"{BASE}/{cid}", headers=CSRF)).status_code == 200
    assert (await admin.get(BASE)).json()["data"]["total"] == 0


async def test_admin_model_search_excludes_unpublished(
    db_session: AsyncSession, admin: httpx.AsyncClient
) -> None:
    await _models(db_session)
    resp = await admin.get("/api/admin/models", params={"q": "model"})
    assert resp.json()["data"] == []
    slugs = [m["slug"] for m in (await admin.get("/api/admin/models")).json()["data"]]
    assert "deepseek-v3-2" in slugs and "old-model" not in slugs


async def test_public_pair_lookup_is_order_independent(
    db_session: AsyncSession, admin: httpx.AsyncClient, db_client: httpx.AsyncClient
) -> None:
    await _models(db_session)
    await _create(admin, "deepseek-v3-2", "qwen3-max")

    for x, y in [("deepseek-v3-2", "qwen3-max"), ("qwen3-max", "deepseek-v3-2")]:
        resp = await db_client.get(f"/internal/v1/model-comparisons/{x}/{y}", headers=AUTH)
        data = resp.json()["data"]
        # 总是返回收录时的顺序，公开站据此跳转到规范网址
        assert (data["model_a"]["slug"], data["model_b"]["slug"]) == ("deepseek-v3-2", "qwen3-max")

    missing = await db_client.get(
        "/internal/v1/model-comparisons/deepseek-v3-2/glm-4-6", headers=AUTH
    )
    assert missing.status_code == 404


async def test_public_list_hides_hidden_pairs_and_unpublished_models(
    db_session: AsyncSession, admin: httpx.AsyncClient, db_client: httpx.AsyncClient
) -> None:
    await _models(db_session)
    await _create(admin, "deepseek-v3-2", "qwen3-max", sort_order=2)
    await _create(admin, "glm-4-6", "deepseek-v3-2", sort_order=1)
    hidden_id = (await _create(admin, "qwen3-max", "glm-4-6")).json()["data"]["id"]
    await admin.post(f"{BASE}/{hidden_id}/hide", headers=CSRF)
    old = (await _create(admin, "old-model", "glm-4-6")).json()
    assert old["code"] == 0  # 后台可以收录未发布模型，但对外不展示

    resp = await db_client.get("/internal/v1/model-comparisons", headers=AUTH)
    pairs = [(c["model_a"]["slug"], c["model_b"]["slug"]) for c in resp.json()["data"]]
    assert pairs == [("glm-4-6", "deepseek-v3-2"), ("deepseek-v3-2", "qwen3-max")]

    resp = await db_client.get(
        "/internal/v1/model-comparisons", params={"model": "qwen3-max"}, headers=AUTH
    )
    assert [c["model_b"]["slug"] for c in resp.json()["data"]] == ["qwen3-max"]
