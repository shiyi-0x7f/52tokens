"""卡网商品标题 → 标准商品 slug（见 data/seed/shop_products.yaml）。

纯规则、无副作用：按优先级依次判断，先命中的生效。归不进任何商品的返回 OTHER。
规则调整后在 tests/fixtures/shop_titles.json 补用例，回归测试会逐条核对。
"""

from app.domains.shops.classify import rules as r
from app.domains.shops.classify.text import has_nearby_negation, matches, normalize_title

# 规则有变化时更新：入库时记录，便于发现需要重新归类的旧报价
CLASSIFIER_VERSION = "2026-10-23.v1"
OTHER = "other-product"


def classify_title(title: str, context: str = "") -> str:
    """context：店铺给的分类名 / 标签，只在标题信息不足时辅助判断。"""
    v = normalize_title(title)
    ctx = normalize_title(context)
    return _classify(v, ctx)


def _classify(v: str, ctx: str) -> str:
    """按优先级排列的规则表：顺序决定冲突时谁说了算，调整顺序要跑回归测试。"""
    if r.is_price_adjustment_listing(v):
        return OTHER
    if r.is_codex_phone_verification(v):
        return "openai-phone-verification"
    if r.is_verification_service(v):
        return r.classify_verification_service(v)
    if r.is_google_play_or_pixel_recharge_product(v):
        return "gemini-pro-recharge"
    if r.is_virtual_card_product(v):
        return "virtual-card"
    if r.is_tool_source_code_product(v):
        return OTHER
    if r.is_mirror_site_product(v):
        return r.classify_mirror_site_product(v)
    if r.is_gift_card_product(v):
        return "gift-card"
    if r.is_dreamina_product(v):
        return "dreamina-account"
    if r.is_x_twitter_engagement_service(v):
        return OTHER
    if r.is_grok_heavy_product(v):
        return "super-grok-heavy"
    if r.is_super_grok_bundle_product(v):
        return "super-grok"
    if r.is_x_twitter_premium_product(v):
        return "x-twitter-premium"
    if r.is_x_twitter_account(v):
        return "x-twitter-account"
    if r.is_telegram_premium_product(v, ctx):
        return "telegram-premium"
    if r.is_telegram_product(v, ctx):
        return "telegram-account"
    if r.is_other_tool(v):
        return r.classify_other_tool(v)
    if r.is_chatgpt_peripheral_service(v):
        return "chatgpt-codex-service"
    if r.is_api_product(v):
        return "openai-api-cdk"
    if r.is_support_service(v):
        return OTHER

    if r.is_gemini_product(v):
        if r.is_gemini_ultra_product(v):
            return "gemini-ultra"
        if r.is_gemini_pro_recharge(v):
            return "gemini-pro-recharge"
        return "gemini-pro-year"

    if r.is_email_account_with_verification_note(v) or r.is_pure_email(v):
        return r.classify_pure_email(v)

    if r.is_claude_product(v):
        if r.is_claude_team_premium(v):
            return "claude-team-premium"
        if r.is_claude_team_standard(v):
            return "claude-team-standard"
        if r.is_claude_max20_product(v):
            return "claude-max-20x"
        if r.is_claude_max5_product(v):
            return "claude-max-5x"
        if matches(
            v, ["pro", "尼区", "月卡", "直充", "代充", "充值", "续费", "订阅", "激活码", "卡密"]
        ):
            return "claude-pro-month"
        return "claude-account"

    if r.is_grok_product(v):
        if r.is_grok_fit_for_super_infrastructure(v):
            return "grok-account"
        if r.is_grok_heavy_product(v):
            return "super-grok-heavy"
        positive_super = matches(v, ["super", "supergrok"]) and not has_nearby_negation(
            v, r"super(?:\s*grok)?"
        )
        if positive_super or matches(v, ["月卡", "年卡", "激活码", "卡密", "直充", "充值"]):
            return "super-grok"
        return "grok-account"

    if r.is_claude_max20_product(v):
        return "claude-max-20x"
    if r.is_claude_max5_product(v):
        return "claude-max-5x"
    if r.is_mixed_chatgpt_pro_tier(v):
        return OTHER
    if r.is_chatgpt_pro20(v):
        return "chatgpt-pro-20x"
    if r.is_chatgpt_pro5(v):
        return "chatgpt-pro-5x"
    if r.is_ambiguous_plus_package(v):
        return OTHER

    if r.is_chatgpt_product(v) and (product := _classify_chatgpt(v)):
        return product

    if r.is_bundled_verification_account(v):
        return OTHER
    if r.is_chatgpt_peripheral_service(v):
        return "chatgpt-codex-service"
    if matches(v, ["gmail", "google 邮箱", "谷歌邮箱", "hotmail", "outlook", "微软邮箱", "邮箱"]):
        return r.classify_pure_email(v)
    if matches(v, ["codex", "api", "cdk", "token", "中转"]) or (
        matches(v, ["额度", "余额"]) and not r.has_account_or_subscription_delivery_signal(v)
    ):
        return "openai-api-cdk"
    if ctx and matches(ctx, ["chatgpt", "openai"]) and matches(v, ["plus"]):
        return "chatgpt-plus-recharge" if r.is_chatgpt_plus_recharge(v) else "chatgpt-plus"
    return OTHER


def _classify_chatgpt(v: str) -> str | None:
    if r.is_chatgpt_pro20(v):
        return "chatgpt-pro-20x"
    if r.is_chatgpt_pro5(v):
        return "chatgpt-pro-5x"
    if r.is_chatgpt_free_account(v) or r.is_negated_plus(v):
        return "chatgpt-free-account"
    if r.is_mixed_chatgpt_pro_tier(v):
        return OTHER
    if r.is_chatgpt_go_product(v):
        return "chatgpt-go"
    if r.is_chatgpt_team_dominant(v):
        return "chatgpt-team-business"
    if r.is_chatgpt_plus_recharge(v):
        return "chatgpt-plus-recharge"
    if r.is_chatgpt_plus(v):
        return "chatgpt-plus"
    if r.is_chatgpt_team(v):
        return "chatgpt-team-business"
    if r.is_chatgpt_account_title(v):
        return "chatgpt-free-account"
    return None
