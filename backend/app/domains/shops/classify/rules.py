"""卡网商品标题的归类规则：一组互相引用的判断函数，入口见 classify/__init__.py。

规则彼此深度互相调用（如 ChatGPT 判断要看邮箱信号、邮箱判断又要看 ChatGPT Plus），
集中放在一个模块里，避免循环导入。所有入参都是 normalize_title 之后的文本。
"""

from app.domains.shops.classify.text import has_nearby_negation, matches, test

# ---------- 通用 ----------


def is_support_service(v: str) -> bool:
    if is_api_product(v):
        return False
    if has_negated_tutorial_mention(v) and is_ai_subscription_or_account_title(v):
        return False
    return matches(
        v,
        [
            "教程",
            "电话卡",
            "手机套餐",
            "代理服务",
            "并发数",
            "安装版",
            "安装教程",
            "登陆教程",
            "登录教程",
        ],
    )


def is_price_adjustment_listing(v: str) -> bool:
    if matches(v, ["定金", "订金", "占位价", "占位链接", "改价专用", "拍下改价"]):
        return True
    if matches(
        v,
        [
            "无需补差价",
            "无须补差价",
            "不需补差价",
            "不需要补差价",
            "不用补差价",
            "无需补差",
            "无需补款",
            "无须补款",
            "不需补款",
            "不需要补款",
            "不用补款",
        ],
    ):
        return False
    return matches(v, ["补差价", "补差链接", "差价链接", "补款", "补款链接", "补拍"])


def has_negated_tutorial_mention(v: str) -> bool:
    return matches(v, ["无教程", "无 教程", "没有教程", "不含教程", "不带教程"])


def is_tool_source_code_product(v: str) -> bool:
    if matches(v, ["源码", "源代码", "脚本源码", "注册机源码"]):
        return True
    if matches(v, ["注册机", "生成器", "工具包"]):
        return not matches(
            v,
            [
                "成品号",
                "账号",
                "账户",
                "积分",
                "额度",
                "power",
                "pro",
                "会员",
                "订阅",
                "月卡",
                "年卡",
            ],
        )
    return False


def is_mirror_site_product(v: str) -> bool:
    if not matches(v, ["镜像站", "镜像", "mirror"]):
        return False
    return matches(v, ["chatgpt", "gpt", "openai", "plus", "claude", "gemini", "grok"])


def classify_mirror_site_product(v: str) -> str:
    if is_grok_product(v):
        return "super-grok-heavy" if is_grok_heavy_product(v) else "super-grok"
    if is_gemini_product(v):
        return "gemini-ultra" if is_gemini_ultra_product(v) else "gemini-pro-year"
    if is_claude_product(v):
        if is_claude_max20_product(v):
            return "claude-max-20x"
        if is_claude_max5_product(v):
            return "claude-max-5x"
        if is_claude_team_premium(v):
            return "claude-team-premium"
        if is_claude_team_standard(v):
            return "claude-team-standard"
        return "claude-pro-month"
    if is_chatgpt_pro20(v):
        return "chatgpt-pro-20x"
    if is_chatgpt_pro5(v):
        return "chatgpt-pro-5x"
    if is_chatgpt_go_product(v):
        return "chatgpt-go"
    if is_chatgpt_team_dominant(v) or is_chatgpt_team(v):
        return "chatgpt-team-business"
    if is_chatgpt_product(v):
        return "chatgpt-plus"
    return "other-product"


def is_gift_card_product(v: str) -> bool:
    if matches(v, ["非礼品卡", "不是礼品卡", "不含礼品卡", "无礼品卡"]):
        return False
    if matches(
        v,
        ["礼品卡", "gift card", "giftcard", "itunes 卡", "itunes卡", "app store 卡", "appstore 卡"],
    ):
        return True
    return matches(v, ["苹果卡", "礼卡"]) and matches(v, ["面额", "usd", "hkd", "try", "充值卡"])


# ---------- 接码 / 验证 ----------


def is_verification_service(v: str) -> bool:
    if is_standalone_verification_service(v):
        return True
    if is_email_account_with_verification_note(v):
        return False
    if is_x_twitter_account_with_login_bundle(v):
        return False
    if is_bundled_verification_account(v):
        return False
    # 标题提到了目标订阅（如「GPT Plus」）但实际卖的是独立的接码服务：
    # 明确的服务 / 取号说法优先，除非同时写了交付账号或订阅
    if is_explicit_verification_service_delivery(v):
        return True
    if is_ai_subscription_or_account_title(v):
        return False
    if matches(
        v,
        ["接码", "收码", "短信验证", "验证码", "手机号验证", "手机验证", "一次性验证", "单次接码"],
    ):
        return True
    return matches(v, ["验证"]) and matches(v, ["手机号", "手机号码", "短信", "接码"])


def is_explicit_verification_service_delivery(v: str) -> bool:
    if not matches(v, ["接码服务", "取号", "取号服务", "短信服务", "手机号服务", "号码服务"]):
        return False
    return not matches(
        v,
        [
            "成品号",
            "成品账号",
            "账号",
            "账户",
            "会员",
            "订阅",
            "月卡",
            "年卡",
            "直充",
            "代充",
            "卡密",
            "自助开通",
            "自动发货",
        ],
    )


def is_bundled_verification_account(v: str) -> bool:
    if is_explicit_verification_service_delivery(v):
        return False
    if has_account_bundle_signal(v) and matches(
        v, ["接码", "收码", "验证码", "手机号", "手机号码", "手机验证"]
    ):
        return True
    return matches(
        v,
        [
            "已接码",
            "已经接码",
            "已完成接码",
            "已手机接码",
            "已接码验证",
            "已手机接码验证",
            "未接码",
            "没接码",
            "自行接码",
            "自己接码",
            "需要自己接码",
            "需要自行接码",
            "codex自己接码",
            "需接码",
            "需使用自行接码",
            "不需要手机验证接码",
            "不需要手机验证",
            "无需手机验证",
            "带接码地址",
            "带接码链接",
            "带电话接码链接",
            "原始接码链接",
            "接码链接",
            "长效接码链接",
            "包含长效接码",
        ],
    )


def is_standalone_verification_service(v: str) -> bool:
    if is_identity_verification_service(v):
        return True
    if matches(v, ["接码自助", "接码 自助", "接码自助卡密", "手机接码自助", "手机接码 自助"]):
        return True
    if matches(
        v,
        [
            "sms 接码",
            "短信接码",
            "短信 接码",
            "实卡接码",
            "实体卡接码",
            "短效接码",
            "短效 接码",
            "收码",
        ],
    ):
        return True
    if matches(v, ["单次接码", "一次性接码", "一次性验证"]):
        return True
    if matches(v, ["手机接码", "手机号验证", "手机验证"]) and matches(
        v, ["号码", "实卡", "自助卡密", "质保1次成功接码"]
    ):
        return True
    if matches(v, ["手机接码"]) and matches(v, ["可绑定", "绑定 3 个", "绑定3个"]):
        return True
    if (
        matches(v, ["短效手机号", "短效 手机号", "手机号"])
        and matches(v, ["google", "谷歌", "gmail", "gemini", "pixel"])
        and matches(v, ["风控", "人机", "验证", "过gemini", "过 gemini"])
        and not has_account_bundle_signal(v)
    ):
        return True
    if matches(
        v,
        [
            "google 反重力可用 claude",
            "codex接码",
            "codex 接码",
            "codex接🐎",
            "codex 接🐎",
            "codex接马",
            "codex 接马",
            "gpt codex 接码",
            "gpt codex接码",
            "openai codex 接码",
            "openai codex接码",
            "google gemini 接码",
            "google gemini接码",
            "gemini 接码",
            "claude 接码",
            "google接码",
            "google 接码",
            "谷歌接码",
            "谷歌邮箱接码",
            "gmail接码",
            "gmail 接码",
            "专用gmail接码",
            "专用 gmail 接码",
        ],
    ) and not has_account_bundle_signal(v):
        return True
    return (
        matches(v, ["反重力可用"])
        and matches(v, ["google", "claude"])
        and not has_account_bundle_signal(v)
    )


def is_identity_verification_service(v: str) -> bool:
    if not has_identity_verification_signal(v):
        return False
    return not has_identity_verification_bundle_signal(v)


def has_identity_verification_signal(v: str) -> bool:
    return matches(v, ["kyc", "人脸验证", "真人认证", "实名认证"]) or test(
        r"(^|[^a-z])persona([^a-z]|$)", v
    )


def has_identity_verification_bundle_signal(v: str) -> bool:
    return matches(
        v,
        [
            "成品号",
            "成品账号",
            "账号",
            "账户",
            "子号",
            "max",
            "pro",
            "team",
            "plus",
            "会员",
            "订阅",
            "月卡",
            "年卡",
            "已过kyc",
            "已过 kyc",
            "以过kyc",
            "以过 kyc",
            "免kyc",
            "免 kyc",
            "免过kyc",
            "免过 kyc",
            "过kyc",
            "过 kyc",
            "已完成kyc",
            "已完成 kyc",
        ],
    )


def has_account_bundle_signal(v: str) -> bool:
    return matches(
        v,
        [
            "成品号",
            "半成品",
            "账号",
            "账户",
            "账密",
            "plus",
            "pro",
            "team",
            "business",
            "月卡",
            "年卡",
            "12个月",
            "一年",
            "会员",
            "订阅",
        ],
    )


def classify_verification_service(v: str) -> str:
    if is_identity_verification_service(v):
        return "identity-verification"
    if matches(v, ["paypal"]):
        return "paypal-phone-verification"
    if matches(v, ["google", "谷歌", "gmail", "gemini", "pixel"]):
        return "google-phone-verification"
    if matches(v, ["openai", "chatgpt", "gpt", "codex"]):
        return "openai-phone-verification"
    return "phone-verification"


def is_codex_phone_verification(v: str) -> bool:
    if not matches(v, ["codex"]):
        return False
    if is_ai_subscription_or_account_title(v):
        return False
    if has_account_bundle_signal(v):
        return False
    return matches(
        v,
        ["接码", "接🦆", "接鸭", "验证码", "短信", "手机号", "手机", "号码", "2fa", "二验", "验证"],
    )


# ---------- 邮箱 ----------

_EMAIL_SIGNALS = [
    "gmail",
    "icloud邮箱",
    "icloud 邮箱",
    "icoud",
    "icoud邮箱",
    "icoud 邮箱",
    "mail邮箱",
    "邮箱",
    "谷歌邮箱",
    "google 邮箱",
    "google邮箱",
    "google个人邮箱",
    "google 个人邮箱",
    "谷歌账号",
    "google 账号",
    "hotmail",
    "outlook",
    "微软邮箱",
    "microsoft 邮箱",
    "教育邮箱",
    "edu 邮箱",
    "学校邮箱",
    "域名邮箱",
    "企业邮箱",
    "子邮箱",
    "oauth2",
]


def has_email_signal(v: str) -> bool:
    return matches(v, _EMAIL_SIGNALS)


def is_email_account_with_verification_note(v: str) -> bool:
    if not has_email_signal(v):
        return False
    if is_ai_subscription_or_account_title(v):
        return False
    if test(r"\b(tg|telegram)\b", v) or matches(v, ["电报"]):
        return False
    if matches(
        v,
        [
            "接码自助",
            "手机接码自助",
            "sms 接码",
            "短信接码",
            "实卡接码",
            "实体卡接码",
            "单次接码",
            "一次性接码",
        ],
    ):
        return False
    if matches(
        v,
        [
            "短效接码",
            "专用gmail接码",
            "专用 gmail 接码",
            "google 接码",
            "google接码",
            "谷歌接码",
            "谷歌邮箱接码",
            "gmail接码",
            "gmail 接码",
        ],
    ):
        return False
    return matches(
        v,
        [
            "老号邮箱",
            "高权重老邮箱",
            "随机地区",
            "带2fa",
            "带 2fa",
            "邮箱带2fa",
            "原始接码链接",
            "带电话接码链接",
            "电话接码链接",
            "不需要手机验证",
            "无需手机验证",
            "会接码的买",
            "登陆需要接码验证",
            "登录需要接码验证",
            "只收验证码",
            "接收验证码",
        ],
    )


def is_pure_email(v: str) -> bool:
    explicit_email = is_icloud_pure_email_product(v) or matches(
        v,
        [
            "gmail",
            "icloud邮箱",
            "icloud 邮箱",
            "icoud邮箱",
            "icoud 邮箱",
            "谷歌邮箱",
            "google 邮箱",
            "google邮箱",
            "google个人邮箱",
            "google 个人邮箱",
            "谷歌账号",
            "google 账号",
            "hotmail",
            "outlook",
            "微软邮箱",
            "microsoft 邮箱",
            "教育邮箱",
            "edu 邮箱",
            "学校邮箱",
            "域名邮箱",
            "企业邮箱",
            "邮箱账号",
            "子邮箱",
            "oauth2",
            ".edu",
        ],
    )
    if not explicit_email:
        return False
    if is_email_only_for_ai_account_setup(v):
        return True
    if is_icloud_backed_ai_account_product(v):
        return False
    if is_email_backed_ai_account_product(v):
        return False
    if matches(v, ["跑gemini", "跑 gemini", "失败的号", "包gcp", "带gcp"]):
        return True
    if matches(
        v,
        [
            "plus 成品",
            "plus成品",
            "plus 独享成品",
            "plus独享成品",
            "plus 会员",
            "plus会员",
            "plus 账号",
            "plus账号",
            "plus 已接码",
            "plus已接码",
            "直接登录codex",
        ],
    ) and not is_icloud_standalone_email_product(v):
        return False
    return not matches(
        v,
        [
            "chatgpt",
            "gpt free",
            "gpt 普号",
            "gpt 白号",
            "gpt 普通",
            "gpt plus",
            "openai 普号",
            "claude",
            "gemini pro",
            "gemini ultra",
            "grok",
            "gpt 账号",
            "gpt账号",
            "gpt 白号",
            "gpt白号",
            "gpt专用",
            "gpt 专用",
            "gptplus",
        ],
    )


def is_email_backed_ai_account_product(v: str) -> bool:
    if not has_email_signal(v):
        return False
    if is_icloud_standalone_email_product(v):
        return False
    if is_email_only_for_ai_account_setup(v):
        return False
    has_chatgpt_signal = matches(v, ["chatgpt", "gpt", "openai", "codex"])
    if is_chatgpt_team_dominant(v):
        return True
    if is_chatgpt_plus(v):
        return True
    if has_chatgpt_signal and is_explicit_email_backed_chatgpt_free_account(v):
        return True
    if has_chatgpt_signal and is_chatgpt_account_title(v):
        return True
    if not has_chatgpt_signal:
        return False
    if matches(
        v,
        [
            "注册gpt专用",
            "注册 gpt 专用",
            "适用于gpt",
            "适用于 gpt",
            "接收邮件",
            "可开gpt",
            "可开 gpt",
            "可开chatgpt",
            "可开 chatgpt",
            "可注册gpt",
            "可注册 gpt",
        ],
    ):
        return False
    return matches(
        v,
        [
            "成品号",
            "成品账号",
            "成品",
            "账号",
            "账户",
            "账密",
            "rt",
            "凭证",
            "json",
            "cpa",
            "反代",
            "sub2api",
            "access token",
            "access_token",
            "质保首登",
            "首登",
            "未接码",
            "已接码",
            "at发货",
        ],
    )


def is_email_only_for_ai_account_setup(v: str) -> bool:
    if not has_email_signal(v):
        return False
    if not matches(v, ["plus", "chatgpt", "gpt", "openai"]):
        return False
    setup_usage_signal = matches(
        v,
        [
            "配合plus",
            "配合 plus",
            "plus自助充值使用",
            "plus 自助充值使用",
            "plus使用",
            "plus 使用",
            "自助充值使用",
            "充值使用",
            "注册gpt专用",
            "注册 gpt 专用",
            "适用于gpt",
            "适用于 gpt",
            "可开gpt",
            "可开 gpt",
            "可注册gpt",
            "可注册 gpt",
        ],
    )
    if not setup_usage_signal:
        return False
    return not matches(
        v,
        [
            "plus 成品",
            "plus成品",
            "plus 独享成品",
            "plus独享成品",
            "plus 会员",
            "plus会员",
            "plus 账号",
            "plus账号",
            "成品号",
            "成品账号",
            "成品会员",
            "独享账号",
            "独享成品",
            "会员",
            "月卡",
            "年卡",
            "订阅",
            "首登",
            "直登",
            "账密",
            "rt",
            "凭证",
            "json",
            "cpa",
            "直充",
            "代充",
            "卡密",
            "自助开通",
            "自动发货",
        ],
    )


def is_explicit_email_backed_chatgpt_free_account(v: str) -> bool:
    if matches(v, ["free", "普号", "白号", "普通号", "普通账号", "空白账号"]):
        return True
    return matches(
        v, ["rt", "access token", "access_token", "token", "已绑定手机", "已绑手机", "手机已验证"]
    ) and matches(v, ["chatgpt", "gpt", "openai", "codex"])


def classify_pure_email(v: str) -> str:
    if matches(v, ["教育邮箱", "edu 邮箱", "学校邮箱", ".edu"]):
        return "education-email"
    if matches(v, ["outlook", "hotmail", "微软邮箱", "microsoft 邮箱", "oauth2", "graph"]):
        return "outlook-account"
    if matches(
        v,
        [
            "gmail",
            "谷歌邮箱",
            "google 邮箱",
            "google邮箱",
            "google个人邮箱",
            "google 个人邮箱",
            "谷歌账号",
            "google 账号",
        ],
    ):
        return "gmail-account"
    if has_email_signal(v) and matches(v, ["谷歌", "google"]):
        return "gmail-account"
    if is_icloud_pure_email_product(v):
        return "icloud-email"
    return "email-account"


_ICLOUD = ["icloud", "icloud邮箱", "icloud 邮箱", "icoud", "icoud邮箱", "icoud 邮箱"]


def is_icloud_standalone_email_product(v: str) -> bool:
    if not matches(v, _ICLOUD):
        return False
    return matches(
        v,
        [
            "隐私邮箱",
            "发货形式为邮箱",
            "开plus",
            "开 plus",
            "绑定专用",
            "取码url",
            "取码 url",
            "plus源头",
            "plus 源头",
        ],
    )


def is_icloud_pure_email_product(v: str) -> bool:
    if not matches(v, _ICLOUD):
        return False
    if is_apple_id_account(v):
        return False
    if is_icloud_backed_ai_account_product(v):
        return False
    return matches(
        v,
        [
            "icloud邮箱",
            "icloud 邮箱",
            "icoud邮箱",
            "icoud 邮箱",
            "icloud隐私邮箱",
            "icloud 隐私邮箱",
            "icoud隐私邮箱",
            "icoud 隐私邮箱",
            "隐私邮箱",
            "母号",
            "子号",
            "子邮箱",
            "取码url",
            "取码 url",
            "取码链接",
            "发货形式为邮箱",
            "绑定专用",
        ],
    )


def is_icloud_backed_ai_account_product(v: str) -> bool:
    if not matches(v, _ICLOUD):
        return False
    if is_icloud_standalone_email_product(v):
        return False
    if not matches(v, ["chatgpt", "gpt", "openai", "codex", "gptplus", "gpt plus", "plus"]):
        return False
    return matches(
        v,
        [
            "成品号",
            "成品账号",
            "成品",
            "账号",
            "账户",
            "月卡",
            "会员",
            "rt",
            "凭证",
            "质保首登",
            "未接码",
            "已接码",
            "2fa",
            "稳定成品",
            "发货格式",
        ],
    )


# ---------- 其他工具 / Telegram / X / Apple ----------


def is_other_tool(v: str) -> bool:
    if (
        is_dreamina_product(v)
        or is_telegram_premium_product(v)
        or is_telegram_product(v)
        or is_x_twitter_engagement_service(v)
        or is_x_twitter_account(v)
        or is_apple_id_account(v)
    ):
        return True
    return matches(
        v,
        [
            "suno",
            "cursor",
            "kiro",
            "windsurf",
            "wind surf",
            "openclaw",
            "open claw",
            "perplexity",
            "dreamina",
            "jimeng",
            "即梦",
            "吉梦",
            "seedance",
            "c档2.0",
            "c档 2.0",
            "c 档2.0",
            "c 档 2.0",
            "telegram",
            "facebook",
            "苹果 id",
            "苹果id",
            "apple id",
            "appleid",
            "苹果账号",
            "apple 账号",
            "美区 id",
            "美区id",
            "土区 id",
            "土区id",
            "日区 id",
            "日区id",
            "港区 id",
            "港区id",
            "外区 id",
            "外区id",
        ],
    )


def classify_other_tool(v: str) -> str:
    if is_dreamina_product(v):
        return "dreamina-account"
    if is_x_twitter_engagement_service(v):
        return "other-product"
    if is_x_twitter_premium_product(v):
        return "x-twitter-premium"
    if is_x_twitter_account(v):
        return "x-twitter-account"
    if is_telegram_premium_product(v):
        return "telegram-premium"
    if is_telegram_product(v):
        return "telegram-account"
    if matches(v, ["cursor"]):
        return "cursor-account"
    if is_kiro_api_credit_product(v):
        return "openai-api-cdk"
    if is_kiro_pro_product(v):
        return "kiro-pro-account"
    if matches(v, ["kiro"]):
        return "kiro-account"
    if matches(v, ["windsurf", "wind surf"]):
        return "windsurf-account"
    if matches(v, ["perplexity"]):
        return "perplexity-account"
    if matches(v, ["suno"]):
        return "suno-account"
    if is_apple_id_account(v):
        return "apple-id-account"
    return "other-product"


def is_dreamina_product(v: str) -> bool:
    return matches(
        v,
        [
            "dreamina",
            "jimeng",
            "即梦",
            "吉梦",
            "seedance",
            "c档2.0",
            "c档 2.0",
            "c 档2.0",
            "c 档 2.0",
        ],
    )


_PHONE_CARD = ["esim", "e sim", "电子卡", "实体卡", "电话卡", "手机卡", "sim 卡"]
_ACCOUNT_WORDS = ["成品号", "账号", "账户", "老号", "白号", "精养", "高权重"]


def is_telegram_product(v: str, context: str = "") -> bool:
    if matches(v, ["飞机大厨", "airplane chefs"]):
        return False
    if is_likely_chatgpt_free_account_title(v):
        return False
    if is_telegram_contact_only(v):
        return False
    if is_telegram_language_pack(v):
        return False
    if is_non_telegram_account_product(v):
        return False
    if matches(v, ["grok", "supergrok", "super grok"]):
        return False
    if is_telegram_premium_product(v, context):
        return False
    if has_telegram_signal(v):
        return True
    if has_telegram_region_account_signal(v):
        return True
    if not context or not has_telegram_signal(context):
        return False
    if matches(v, _PHONE_CARD):
        return False
    return matches(v, [*_ACCOUNT_WORDS, "星星"])


def has_telegram_signal(v: str) -> bool:
    return test(r"\b(tg|telegram)\b", v) or matches(
        v, ["电报", "飞机号", "飞机账号", "飞机成品", "telegram 星星"]
    )


def is_telegram_language_pack(v: str) -> bool:
    return has_telegram_signal(v) and matches(v, ["中文包", "语言包", "汉化包", "官方中文包"])


def has_telegram_region_account_signal(v: str) -> bool:
    if matches(
        v,
        [
            *_PHONE_CARD,
            "手机号",
            "号码",
            "接码",
            "upi",
            "邮箱",
            "mail",
            "hotmail",
            "outlook",
            "gcp",
            "apple id",
            "appid",
            "app id",
            "id 独享",
            "id账号",
            "id 账号",
        ],
    ):
        return False
    if is_known_non_telegram_platform_account(v):
        return False
    if not test(r"(?:^|[^0-9])(?:\+|➕)1(?:[^0-9]|$)|(?:\+|➕)91|区号91", v):
        return False
    return matches(v, [*_ACCOUNT_WORDS, "抗风控", "满月", "新号"])


def is_telegram_premium_product(v: str, context: str = "") -> bool:
    if is_telegram_contact_only(v):
        return False
    if matches(v, ["飞机大厨", "airplane chefs"]):
        return False
    if has_telegram_stars_signal(v):
        return True
    has_telegram = has_telegram_signal(v) or bool(context and has_telegram_signal(context))
    if not has_telegram:
        return False
    return matches(
        v,
        [
            "telegram premium",
            "tg premium",
            "电报 premium",
            "telegram pro",
            "tg pro",
            "premium会员",
            "premium 会员",
            "会员代开",
            "会员兑换码",
            "会员 3个月",
            "会员 6个月",
            "会员 12个月",
            "用户名赠送会员",
            "电报三月会员",
            "电报六月会员",
            "电报一年会员",
            "三个月订阅",
            "六个月订阅",
            "一年订阅",
        ],
    )


def has_telegram_stars_signal(v: str) -> bool:
    return (has_telegram_signal(v) and test(r"星星|stars?", v)) or matches(
        v, ["telegram stars", "telegram 星星", "星星兑换码", "星星代充"]
    )


def is_non_telegram_account_product(v: str) -> bool:
    return matches(
        v,
        [
            "linkedin",
            "领英",
            "instagram",
            "tiktok",
            "tik tok",
            "facebook",
            "figma",
            "whatsapp",
            "line账号",
            "全地区tiktok",
        ],
    )


def is_known_non_telegram_platform_account(v: str) -> bool:
    return matches(
        v,
        [
            "chatgpt",
            "openai",
            "gpt",
            "claude",
            "gemini",
            "google",
            "gmail",
            "icloud",
            "apple",
            "grok",
            "cursor",
            "kiro",
            "windsurf",
            "perplexity",
            "suno",
            "midjourney",
            "discord",
            "github",
            "spotify",
            "netflix",
            "youtube",
        ],
    )


def is_telegram_contact_only(v: str) -> bool:
    if not matches(
        v,
        [
            "tg客服",
            "tg 客服",
            "telegram客服",
            "telegram 客服",
            "联系tg",
            "联系 tg",
            "联系telegram",
            "联系 telegram",
        ],
    ):
        return False
    return not matches(
        v,
        ["telegram账号", "telegram 账号", "tg账号", "tg 账号", "电报账号", "飞机号", "成品号"],
    )


def is_x_twitter_account(v: str) -> bool:
    if not has_x_twitter_signal(v):
        return False
    if matches(v, ["twitter", "推特", "x 推特", "x/twitter", "x-twitter"]):
        return True
    return not (
        is_claude_product(v) or is_gemini_product(v) or is_grok_product(v) or is_chatgpt_product(v)
    )


def has_x_twitter_signal(v: str) -> bool:
    if matches(
        v, ["twitter", "推特", "x premium", "x账号", "x 账号", "x 推特", "x/twitter", "x-twitter"]
    ):
        return True
    return test(r"\bx\s*(premium|account|账号|会员|推特)\b", v)


def is_x_twitter_premium_product(v: str) -> bool:
    if not has_x_twitter_signal(v):
        return False
    return matches(
        v,
        [
            "x premium",
            "twitter premium",
            "推特 premium",
            "premium+",
            "premium plus",
            "推特会员",
            "x 会员",
            "蓝标",
            "蓝v",
            "蓝 v",
            "会员直充",
            "会员代开",
            "会员卡密",
            "月卡",
            "年卡",
            "年度会员",
            "自助卡密",
            "激活码",
            "cdk",
            "ios充值",
            "ios 充值",
        ],
    )


def is_x_twitter_engagement_service(v: str) -> bool:
    if not has_x_twitter_signal(v):
        return False
    if is_x_twitter_premium_product(v):
        return False
    if matches(
        v,
        [
            "账号",
            "账户",
            "老号",
            "新号",
            "三绑",
            "双绑",
            "2fa",
            "token",
            "登录",
            "登陆",
            "邮箱绑定",
            "手机验证",
        ],
    ):
        return False
    return matches(v, ["涨粉", "粉丝", "关注", "转发", "点赞", "评论", "浏览", "互动"])


def is_x_twitter_account_with_login_bundle(v: str) -> bool:
    if not is_x_twitter_account(v):
        return False
    return matches(
        v,
        [
            "账号",
            "账户",
            "三绑",
            "token",
            "登录",
            "登陆",
            "2fa",
            "premium",
            "会员",
            "hotmail邮箱可用",
        ],
    )


def is_apple_id_account(v: str) -> bool:
    if matches(v, ["apple id", "appleid", "苹果 id", "苹果id", "苹果账号", "apple 账号"]):
        return True
    if matches(
        v,
        [
            "美区id",
            "美区 id",
            "土区id",
            "土区 id",
            "日区id",
            "日区 id",
            "港区id",
            "港区 id",
            "外区id",
            "外区 id",
        ],
    ):
        return True
    if test(
        r"(?:台湾|香港|菲律宾|美国|日本|韩国|土耳其|土区|美区|日区|港区|台区|菲区|外区)\s*id", v
    ) and matches(v, ["icloud", "icoud", "app", "账号", "账户", "独享", "老号", "成品", "可转区"]):
        return True
    return (
        matches(v, ["id"])
        and matches(v, ["苹果", "apple"])
        and matches(v, ["账号", "账户", "成品号", "地区"])
    )


# ---------- API / 额度 ----------


def is_api_product(v: str) -> bool:
    if is_codex_phone_verification(v):
        return False
    if is_chatgpt_peripheral_service(v):
        return False
    if is_google_play_or_pixel_recharge_product(v):
        return False
    if has_explicit_api_product_signal(v):
        return True
    if is_chatgpt_account_or_subscription_dominant(v):
        return False
    if is_chatgpt_team(v):
        return False
    if is_claude_product(v) and matches(
        v, ["team", "席位", "标准席位", "高级席位", "1.25x", "1.25倍", "6.25x", "6.25倍"]
    ):
        return False
    if matches(v, ["gemini pro", "google ai pro"]) and matches(v, ["一年", "订阅", "cdk"]):
        return False
    if (
        is_chatgpt_transit_or_api_credit_product(v)
        or is_kiro_api_credit_product(v)
        or is_model_api_credit_product(v)
        or is_model_pool_credit_product(v)
        or is_claude_code_credit_product(v)
    ):
        return True
    return matches(v, ["额度"]) and matches(
        v, ["claude", "gemini", "gpt", "codex", "openai", "ai 平台"]
    )


_TOTAL_DOLLARS = r"(?:总共|共)\s*\d+\s*(?:刀|美元|美金)"
_PLUS_CHANNEL = [
    "plus渠道",
    "plus 渠道",
    "plus号池",
    "plus 号池",
    "老plus渠道",
    "老 plus 渠道",
    "30天有效期",
]


def has_explicit_api_product_signal(v: str) -> bool:
    if test(r"(^|[^a-z])api([^a-z]|$).{0,12}\d+\s*(?:刀|美元|美金|\$)", v):
        return True
    if matches(v, ["apikey", "api key", "api-key"]):
        return True
    if matches(v, ["claude/gpt/gemini中转站", "中转余额", "中转 gpt", "api中转", "api 中转"]):
        return True
    if (
        matches(v, ["中转"])
        and (matches(v, ["号池", "余额", "api", "额度"]) or has_money_amount(v))
        and not has_account_or_subscription_delivery_signal(v)
    ):
        return True
    if matches(v, ["中转站"]) and not has_account_or_subscription_delivery_signal(v):
        return True
    if matches(v, ["号池"]) and (
        matches(v, ["api", "codex", "额度", "余额", "中转"]) or has_money_amount(v)
    ):
        return True
    if test(_TOTAL_DOLLARS, v) and matches(v, _PLUS_CHANNEL):
        return True
    if matches(v, ["中转api", "中转 api"]):
        return True
    if matches(v, ["兑换码"]) and matches(
        v, ["api", "额度", "100刀", "200刀", "300刀", "1000刀", "2100刀", "官方1:1"]
    ):
        return True
    if matches(v, ["codexapi", "codex api", "codex 授权", "codex 授權"]):
        return True
    if matches(v, ["gpt api", "openai api", "geminiapi", "gemini api"]):
        return True
    if matches(v, ["api 额度", "api额度", "api 100刀", "api 50刀", "api 300刀"]):
        return True
    if matches(v, ["余额兑换", "余额 兑换", "倍率"]):
        return True
    return matches(v, ["余额充值", "充值余额", "美元额度", "美金额度", "刀额度"])


def is_kiro_api_credit_product(v: str) -> bool:
    if not matches(v, ["kiro"]):
        return False
    if matches(v, ["注册机", "生成器", "源码"]):
        return False
    if matches(v, ["号池"]):
        return True
    if matches(v, ["claude code"]) and has_money_amount(v):
        return True
    if matches(v, ["刀额度", "美元额度", "美金额度"]):
        return True
    return test(r"(?:\d+\s*(?:刀|美元|美金)|\d+\s*\$)\s*额度", v)


def has_account_or_subscription_delivery_signal(v: str) -> bool:
    return matches(
        v,
        [
            "成品号",
            "库存号",
            "账号",
            "账户",
            "账密",
            "首登",
            "直登",
            "质保首登",
            "老邮箱",
            "已验证",
            "月卡",
            "年卡",
            "会员",
            "订阅",
            "直充",
            "代充",
            "卡密",
            "自助开通",
            "自动发货",
            "接码",
            "带rt",
            "带 rt",
            "导入中转站",
            "直接导入",
        ],
    )


def is_google_play_or_pixel_recharge_product(v: str) -> bool:
    if not matches(v, ["pixel", "google", "谷歌", "play", "google play"]):
        return False
    if has_explicit_non_gemini_product_signal(v):
        return False
    return matches(v, ["cdk", "cdkey", "兑换", "充值", "礼品卡", "提取链接", "优惠链接", "绑卡"])


def has_explicit_non_gemini_product_signal(v: str) -> bool:
    return is_claude_product(v) or is_grok_product(v) or is_chatgpt_product(v)


def is_chatgpt_transit_or_api_credit_product(v: str) -> bool:
    if not matches(v, ["chatgpt", "gpt", "openai", "codex", "plus"]):
        return False
    if (
        matches(v, ["倍率"])
        and matches(v, ["plus", "pro", "gpt", "chatgpt", "openai", "codex"])
        and test(r"(?:\d+\s*(?:刀|美元|美金)|\d+\s*\$)", v)
    ):
        return True
    if matches(v, ["中转api", "中转 api", "api中转", "api 中转", "中转余额", "中转站额度"]) or test(
        r"(api|codex)\s*(\d+\s*)?(刀|美元|美金).*(额度|余额|兑换码|刀卡)", v
    ):
        return True
    if matches(v, ["号池"]) and matches(
        v, ["api", "codex", "额度", "余额", "刀", "美元", "美金", "中转"]
    ):
        return True
    return test(_TOTAL_DOLLARS, v) and matches(v, _PLUS_CHANNEL)


def is_model_pool_credit_product(v: str) -> bool:
    if not matches(v, ["池", "号池", "pool"]):
        return False
    if not matches(v, ["claude", "gemini", "gpt", "chatgpt", "codex", "openai"]):
        return False
    if matches(v, ["team", "团队", "席位", "seat"]):
        return False
    if (
        is_claude_product(v)
        and matches(v, ["max", "pro"])
        and not matches(v, ["月卡", "月会员", "年卡", "订阅", "成品号", "账号", "直充", "代充"])
    ):
        return True
    if matches(v, ["额度", "中转", "api", "刀", "美元", "美金", "余额"]):
        return True
    if matches(v, ["月会员", "会员兑换码", "月卡", "年卡", "订阅"]):
        return False
    return matches(v, ["兑换码", "token"])


def is_claude_code_credit_product(v: str) -> bool:
    if not matches(v, ["claude code"]):
        return False
    return matches(v, ["每天", "有效期", "额度", "不限量额度"]) and has_money_amount(v)


def is_model_api_credit_product(v: str) -> bool:
    if not matches(v, ["codex api", "openai api", "chatgpt api", "gpt api"]):
        return False
    if matches(v, ["余额兑换码", "余额 兑换码", "兑换码", "额度", "刀卡", "美元额度", "美金额度"]):
        return True
    return test(r"\d+\s*\$\s*余额", v) or test(r"\d+\s*\$\s*余额兑换码", v)


def has_money_amount(v: str) -> bool:
    return matches(v, ["刀", "美元", "美金"]) or test(r"\d+\s*\$", v)


def is_virtual_card_product(v: str) -> bool:
    if matches(v, ["paypal接码", "paypal 接码"]):
        return False
    if matches(
        v,
        [
            "visa",
            "mastercard",
            "虚拟卡",
            "虚拟信用卡",
            "bin 卡",
            "485954",
            "美国虚拟卡",
            "paypal 美国虚拟卡",
        ],
    ):
        return True
    if is_zero_or_one_dollar_card(v):
        return True
    return matches(v, ["美国卡", "卡头"]) and not matches(
        v, ["chatgpt", "claude", "gemini", "grok"]
    )


def is_zero_or_one_dollar_card(v: str) -> bool:
    return test(r"(^|[^\d])[01]\s*刀\s*卡(?!\d)", v)


# ---------- ChatGPT 周边服务 ----------


def is_chatgpt_peripheral_service(v: str) -> bool:
    has_payment_link_extraction = is_chatgpt_payment_link_extraction_service(v)
    has_self_service_recharge = is_chatgpt_self_service_recharge(v)
    if (
        not has_payment_link_extraction
        and not has_self_service_recharge
        and not matches(v, ["codex", "chatgpt", "gpt", "openai", "plus"])
    ):
        return False
    if is_codex_phone_verification(v):
        return False
    if is_api_product_core_signal(v):
        return False
    if has_self_service_recharge:
        has_account_delivery = matches(
            v, ["成品号", "成品账号", "成品帐号", "独享账号", "独享账户", "账密", "首登", "直登"]
        )
        has_own_account = matches(
            v,
            [
                "非成品",
                "自备账号",
                "自备号",
                "自己账号",
                "自己的账号",
                "自己号",
                "到自己账号",
                "冲自己号",
                "充值自己号",
                "给自己号",
                "任何账号可充",
                "kakao自助充值",
            ],
        )
        return not (has_account_delivery and not has_own_account)
    if has_payment_link_extraction:
        if matches(v, ["代付代扫", "代付服务", "代扫服务"]):
            return True
        return not matches(v, ["成品号", "账号", "账户", "账密", "月卡", "会员", "直充", "代充"])

    has_peripheral_signal = (
        matches(v, ["重置额度", "额度重置", "刷新额度", "恢复额度"])
        or (matches(v, ["重置"]) and matches(v, ["plus", "pro", "额度"]))
        or matches(
            v, ["长链提取", "长链接提取", "链接提取", "提取服务", "提取服务包", "长链服务包"]
        )
        or (
            matches(v, ["服务包"])
            and matches(v, ["长链", "提取", "codex", "chatgpt", "gpt", "plus"])
        )
    )
    if not has_peripheral_signal:
        return False
    return not matches(
        v, ["成品号", "账号", "账户", "账密", "月卡", "会员", "直充", "代充", "卡密", "cdk"]
    )


def is_chatgpt_self_service_recharge(v: str) -> bool:
    if is_email_only_for_ai_account_setup(v):
        return False
    if is_mixed_chatgpt_pro_tier(v):
        return False
    if (
        is_chatgpt_go_product(v)
        or is_chatgpt_team_dominant(v)
        or is_chatgpt_pro20(v)
        or is_chatgpt_pro5(v)
    ):
        return False
    if matches(
        v,
        ["gemini", "google ai", "claude", "grok", "perplexity", "telegram", "twitter", "x premium"],
    ):
        return False
    if not matches(v, ["chatgpt", "gpt", "openai", "plus", "kakao"]):
        return False
    return matches(
        v,
        [
            "自助充值",
            "自助开通",
            "自助卡密",
            "卡密自助",
            "自助激活",
            "自动充值",
            "自动开通",
            "自动激活",
            "全自动充值",
            "全自动开通",
            "全自动激活",
        ],
    )


def is_chatgpt_payment_link_extraction_service(v: str) -> bool:
    has_payment_method = matches(v, ["upi", "ideal", "i deal", "ide al", "paypal", "荷兰渠道"])
    has_chatgpt_subscription = matches(v, ["chatgpt", "gpt", "openai", "plus"])
    if not has_payment_method and not has_chatgpt_subscription:
        return False
    return matches(
        v,
        [
            "提链",
            "提炼",
            "提取链接",
            "链接提取",
            "长链提取",
            "长链接提取",
            "扫码对接",
            "提取upi支付二维码",
            "提取 upi 支付二维码",
            "提取支付二维码",
            "支付二维码",
            "二维码生成率",
            "支付链接",
            "提链服务",
            "代付代扫",
            "代付服务",
            "代扫服务",
        ],
    )


def is_api_product_core_signal(v: str) -> bool:
    return matches(
        v,
        [
            "apikey",
            "api key",
            "api-key",
            "codex api",
            "openai api",
            "chatgpt api",
            "gpt api",
            "中转api",
            "中转 api",
            "api中转",
            "api 中转",
            "中转余额",
            "中转站额度",
            "余额兑换码",
            "api 额度",
            "api额度",
            "api 100刀",
            "api 50刀",
            "api 300刀",
        ],
    )


# ---------- Claude / Gemini / Grok / Kiro ----------


def is_claude_product(v: str) -> bool:
    return matches(v, ["claude", "克劳德"])


_OTHER_AI = ["chatgpt", "gpt", "openai", "gemini", "grok"]


def is_claude_max20_product(v: str) -> bool:
    if matches(v, _OTHER_AI):
        return False
    has_max = matches(v, ["max"])
    if not is_claude_product(v) and not has_max:
        return False
    if matches(v, ["max20", "max 20", "20x", "x20", "20倍", "20 max", "20x max", "20xmax"]):
        return True
    return has_max and test(r"(?:max.*200|200\s*(?:usd|刀|美金|美元|订阅))", v)


def is_claude_max5_product(v: str) -> bool:
    if matches(v, _OTHER_AI):
        return False
    has_max = matches(v, ["max"])
    if not is_claude_product(v) and not has_max:
        return False
    if is_claude_max20_product(v):
        return False
    if matches(v, ["max5", "max 5", "5x", "x5", "5倍", "5 max", "5x max", "5xmax"]):
        return True
    return has_max and test(r"(?:max.*100|100\s*(?:usd|刀|美金|美元|订阅))", v)


def is_claude_team_product(v: str) -> bool:
    return is_claude_product(v) and matches(v, ["team", "团队", "席位", "seat"])


_PREMIUM_MULTIPLIER = ["6.25x", "6.25 x", "6.25倍", "6.25 倍"]


def is_claude_team_premium(v: str) -> bool:
    if not is_claude_product(v):
        return False
    if not matches(v, ["premium", "高级席位", "高级", *_PREMIUM_MULTIPLIER]):
        return False
    return is_claude_team_product(v) or matches(v, _PREMIUM_MULTIPLIER)


def is_claude_team_standard(v: str) -> bool:
    if not is_claude_team_product(v):
        return False
    if is_claude_team_premium(v):
        return False
    return matches(
        v,
        [
            "team",
            "团队",
            "席位",
            "seat",
            "standard",
            "标准",
            "1.25x",
            "1.25 x",
            "1.25倍",
            "1.25 倍",
        ],
    )


def is_gemini_product(v: str) -> bool:
    if matches(v, ["失败的号", "失败号", "跑gemini pro 失败", "跑 gemini pro 失败"]):
        return False
    if matches(v, ["gcp", "反重力"]) and matches(v, ["pro12个月", "pro 12个月", "12个月", "一年"]):
        return True
    return matches(v, ["gemini", "google ai", "ai ultra"]) or (
        matches(v, ["pixel"]) and matches(v, ["pro", "订阅"])
    )


def is_gemini_ultra_product(v: str) -> bool:
    if is_gemini_pro_ultra_mixed_title(v):
        return False
    if matches(v, ["google ai ultra", "gemini ultra", "ai ultra", "企业 ultra", "企业ultra"]):
        return True
    if matches(
        v, ["250美元", "250 美元", "250美金", "250 美金", "250刀", "45k", "25k"]
    ) and matches(v, ["gemini", "google ai", "ultra", "flow"]):
        return True
    if matches(v, ["gemini pro", "google ai pro", "ai pro", "pro 12个月", "pro12个月"]):
        return False
    return matches(v, ["flow"]) and matches(v, ["gemini", "google ai", "ultra"])


def is_gemini_pro_ultra_mixed_title(v: str) -> bool:
    return matches(
        v,
        [
            "pro ultra",
            "pro uitra",
            "ai pro ultra",
            "ai pro uitra",
            "gemini ai pro ultra",
            "gemini ai pro uitra",
        ],
    )


def is_gemini_pro_recharge(v: str) -> bool:
    if not is_gemini_product(v):
        return False
    if is_gemini_ultra_product(v):
        return False
    if not matches(
        v,
        [
            "自助充值",
            "自助开通",
            "充值",
            "代充",
            "直充",
            "开通",
            "cdk",
            "卡密",
            "兑换码",
            "优惠链接",
            "提取",
            "激活链接",
            "激活码",
            "一次卡",
            "绑卡",
            "订阅",
            "充自己号",
            "自备账号",
            "自己号",
        ],
    ):
        return False
    return not (is_gemini_pro_account(v) and not is_gemini_self_account_recharge(v))


def is_gemini_self_account_recharge(v: str) -> bool:
    return matches(
        v,
        [
            "自备账号",
            "自备 账号",
            "自己号",
            "自己的号",
            "充自己号",
            "给自己号",
            "自助充值",
            "自助开通",
            "代充",
            "直充",
            "cdk",
            "优惠链接",
            "提取",
            "激活链接",
            "一次卡",
            "绑卡",
        ],
    )


def is_gemini_pro_account(v: str) -> bool:
    return matches(
        v,
        [
            "成品号",
            "成品",
            "账号",
            "账户",
            "个人账号",
            "邮箱",
            "gmail",
            "google 账号",
            "谷歌账号",
            "pixel",
            "首登",
            "直登",
            "独享",
            "家庭组",
            "随机地区",
            "美区",
            "老邮箱",
            "老号",
            "带2fa",
            "带 2fa",
            "长效接码",
        ],
    )


def is_grok_product(v: str) -> bool:
    return matches(v, ["grok", "supergrok"])


def is_grok_heavy_product(v: str) -> bool:
    if not is_grok_product(v):
        return False
    if has_nearby_negation(v, "heavy"):
        return False
    return matches(
        v,
        [
            "heavy",
            "grok heavy",
            "heavy grok",
            "grok super heavy",
            "super grok heavy",
            "supergrok heavy",
        ],
    )


def is_super_grok_bundle_product(v: str) -> bool:
    if not is_grok_product(v):
        return False
    if is_grok_heavy_product(v):
        return False
    if has_nearby_negation(v, r"super(?:\s*grok)?"):
        return False
    return matches(
        v,
        [
            "super grok",
            "supergrok",
            "grok super",
            "自带super grok",
            "自带 super grok",
            "带supergrok",
            "带 supergrok",
            "带super grok",
            "带 super grok",
            "赠送super grok",
            "赠送 super grok",
            "x premium super grok",
            "x premium supergrok",
            "x premium+ super grok",
            "x premium+ supergrok",
        ],
    )


def is_grok_fit_for_super_infrastructure(v: str) -> bool:
    if not is_grok_product(v):
        return False
    if matches(
        v, ["super grok", "supergrok", "3天", "三天", "7天", "七天", "月卡", "月会员", "会员号"]
    ):
        return False
    if not matches(
        v, ["适合super", "适合 super", "取邮件api", "取邮件 api", "长效微软邮箱", "账号 sso"]
    ):
        return False
    return matches(v, ["普号", "free", "sso", "邮箱", "取邮件"])


_KIRO_HIGH = [
    "1000",
    "2000",
    "5000",
    "1w",
    "10000",
    "100刀",
    "200刀",
    "500刀",
    "100$",
    "200$",
    "500$",
]


def is_kiro_pro_product(v: str) -> bool:
    if not matches(v, ["kiro"]):
        return False
    if matches(v, ["普号", "free", "固定50", "50额度", "kirors", "kiro rs"]) and not matches(
        v, ["kiro pro", "kiro pro+", "power", "promax", *_KIRO_HIGH]
    ):
        return False
    return matches(
        v,
        [
            "kiro pro",
            "kiro pro+",
            "kiro pro max",
            "kiro promax",
            "pro+",
            "promax",
            "power",
            "积分",
            "额度号",
            "额度",
            "可超额",
            *_KIRO_HIGH,
        ],
    )


# ---------- ChatGPT ----------


def is_chatgpt_product(v: str) -> bool:
    if matches(v, ["gemini", "claude", "grok"]):
        return False
    if matches(v, ["steam"]):
        return False
    if is_chatgpt_pro20(v) or is_chatgpt_pro5(v):
        return True
    if is_chatgpt_go_product(v):
        return True
    if is_likely_chatgpt_free_account_title(v):
        return True
    return matches(
        v, ["chatgpt", "gpt", "openai", "codex", "plus", "team", "business", "t5", "k12"]
    )


def is_ai_subscription_or_account_title(v: str) -> bool:
    if not matches(
        v,
        [
            "chatgpt",
            "gpt",
            "openai",
            "codex",
            "claude",
            "gemini",
            "grok",
            "plus",
            "team",
            "business",
        ],
    ):
        return False
    return matches(
        v,
        [
            "plus",
            "pro",
            "team",
            "business",
            "free",
            "普号",
            "白号",
            "普通号",
            "普通账号",
            "成品号",
            "账号",
            "兑换号",
            "cdk",
            "直充",
            "充值",
            "卡密",
            "月卡",
            "会员",
        ],
    )


def is_chatgpt_free_account(v: str) -> bool:
    if is_likely_chatgpt_free_account_title(v):
        return True
    if matches(v, ["free", "普号", "白号", "普通号", "普通账号", "空白账号"]):
        return True
    return matches(v, ["长效"]) and not matches(v, ["plus", "pro", "team", "business"])


def is_likely_chatgpt_free_account_title(v: str) -> bool:
    if not matches(v, ["free", "普号", "普通号", "普通账号", "白号"]):
        return False
    if matches(
        v,
        [
            "google",
            "gmail",
            "谷歌",
            "pixel",
            "tiktok",
            "tik tok",
            "facebook",
            "instagram",
            "telegram",
            "twitter",
            "推特",
            "steam",
            "苹果",
            "apple",
        ],
    ):
        return False
    if matches(v, ["chatgpt", "gpt", "openai", "codex"]):
        return True
    return matches(
        v,
        [
            "rt",
            "json",
            "cpa",
            "sub2api",
            "已接码",
            "已经接码",
            "质保首登",
            "高额度",
            "高端",
            "优质",
            "成品号",
            "直登",
        ],
    )


def is_chatgpt_go_product(v: str) -> bool:
    if matches(v, ["opencode", "open code"]):
        return False
    has_chatgpt = matches(v, ["chatgpt", "gpt", "openai"])
    has_standalone_go = test(r"\bgo\b", v) and matches(
        v,
        ["月卡", "年卡", "直充", "充值", "激活", "会员", "订阅", "独享", "自助", "卡密", "成品号"],
    )
    if not has_chatgpt and not has_standalone_go:
        return False
    if matches(v, ["google", "gojek", "gopay"]):
        return False
    return test(r"\bgo\b", v) or test(r"\bgo(?=\d|月|年|直充|充值|激活|会员|订阅|独享)", v)


def is_ambiguous_plus_package(v: str) -> bool:
    if not matches(v, ["plus"]):
        return False
    if matches(
        v,
        [
            "chatgpt plus",
            "gpt plus",
            "plus 月卡",
            "plus 一个月",
            "plus 账号",
            "plus 成品号",
            "plus 日抛",
            "plus 直充",
            "plus 代充",
            "plus 卡密",
            "plus 自助",
            "网页版plus",
            "网页端",
            "icloud邮箱plus",
            "保首登",
            "福利号",
            "特价plus",
        ],
    ):
        return False
    if test(r"plus\s*\d+\s*(刀|美元|美金|万)", v):
        return True
    if test(r"纯\s*plus", v) and test(r"\d+\s*(刀|美元|美金|万)", v):
        return True
    return matches(v, ["限时体验版本", "不限时"]) and "plus" in v


def is_chatgpt_plus(v: str) -> bool:
    if is_email_only_for_ai_account_setup(v):
        return False
    has_chatgpt = matches(v, ["chatgpt", "gpt", "openai"])
    has_plus = matches(v, ["plus"])
    if not has_chatgpt and not has_plus:
        return False
    if matches(v, ["pro"]) and not matches(v, ["plus"]):
        return False
    if is_chatgpt_go_product(v):
        return False
    if has_chatgpt and has_plus:
        return True
    if has_plus and not has_chatgpt:
        return matches(
            v,
            [
                "plus 成品",
                "plus成品",
                "plus 独享成品",
                "plus独享成品",
                "plus 会员",
                "plus会员",
                "plus 账号",
                "plus账号",
                "plus 月卡",
                "plus月卡",
                "plus 一个月",
                "plus一个月",
                "plus 直充",
                "plus直充",
                "plus 代充",
                "plus代充",
                "plus 卡密",
                "plus卡密",
                "plus 自助",
                "plus自助",
                "gpt plus",
                "成品 plus",
                "成品号",
                "独享账号",
                "账号",
                "账密",
                "首登",
                "直登",
                "质保首登",
                "rt",
                "凭证",
                "已接码",
                "会员",
                "月卡",
                "订阅",
                "直充",
                "充值",
                "卡密",
                "cc 渠道",
                "谷歌正规付款",
            ],
        )
    return matches(
        v,
        [
            "ios土区",
            "土区 ios",
            "土区",
            "自助卡密",
            "续费一个月",
            "一个月卡密",
            "一个月 成品号",
            "一个月",
            "月卡",
            "订阅",
            "直充",
            "充值",
            "卡密",
            "cc 渠道",
            "谷歌正规付款",
        ],
    )


def has_chatgpt_plus_recharge_official_direct_signal(v: str) -> bool:
    return test(
        r"官方直充|官方充值|官方代充|官方订阅|正价(?:代充|充值|直充|实付)?|正规充值|正规官方|正规卡付"
        r"|正规卡冲|官网直充|官网直冲|官网代充|真实付费(?:开通|充值)?",
        v,
    )


def is_chatgpt_plus_recharge(v: str) -> bool:
    if not is_chatgpt_plus(v):
        return False
    if has_chatgpt_plus_account_delivery_signal(v):
        return False
    if is_chatgpt_plus_pix_trial(v):
        return False
    return has_chatgpt_plus_recharge_official_direct_signal(v)


def has_chatgpt_plus_account_delivery_signal(v: str) -> bool:
    if matches(
        v,
        [
            "自备账号",
            "自备号",
            "自己账号",
            "自己的账号",
            "自己号",
            "自己的号",
            "到自己账号",
            "充值到自己账号",
            "充自己号",
            "给自己号",
            "任何账号可充",
        ],
    ):
        return False
    if matches(
        v,
        [
            "成品号",
            "成品账号",
            "成品帐号",
            "独享账号",
            "独享账户",
            "账密",
            "首登",
            "直登",
            "未接码",
            "已接码",
            "网页号",
            "半成品",
            "母号邮箱",
            "邮箱随机发货",
            "拿到后立刻改密码",
            "拿到后改密码",
            "修改密码",
            "改密码",
            "支持登录codex",
            "支持登录 codex",
            "直接登录codex",
            "直接登录 codex",
            "登录codex",
            "登录 codex",
            "带2fa",
            "带 2fa",
            "2fa",
            "二验",
        ],
    ):
        return True
    has_email_credential = matches(
        v,
        [
            "gmail邮箱",
            "gmail 邮箱",
            "icloud邮箱",
            "icloud 邮箱",
            "outlook邮箱",
            "outlook 邮箱",
            "微软邮箱",
            "谷歌邮箱",
        ],
    )
    has_login_or_credential = matches(
        v,
        [
            "支持登录",
            "可以登录",
            "可登录",
            "登录codex",
            "登录 codex",
            "可网页",
            "动态家宽注册",
            "2fa",
            "二验",
        ],
    )
    return has_email_credential and has_login_or_credential


_PIX_TRIAL_SIGNALS = [
    "试用",
    "新号",
    "老号",
    "不包二验",
    "未接码",
    "已接码",
    "首登",
    "质保48小时",
    "质保两天",
    "质保首登",
    "渠道非成品",
    "自备账号",
    "自己账号",
    "有team不能冲",
]


def is_chatgpt_plus_pix_trial(v: str) -> bool:
    if matches(v, ["pix"]):
        if matches(v, ["巴西", "巴西渠道"]):
            return True
        return matches(v, [*_PIX_TRIAL_SIGNALS, "巴西老哥", "巴西渠道"])
    return matches(v, ["巴西渠道"]) and matches(v, _PIX_TRIAL_SIGNALS)


def is_chatgpt_account_title(v: str) -> bool:
    if not matches(v, ["chatgpt", "gpt", "openai", "codex"]):
        return False
    if matches(v, ["plus", "pro", "team", "business", "t5"]):
        return False
    return matches(v, ["成品号", "账号", "独享号", "直登", "日抛", "网页号", "半成品"])


def is_chatgpt_account_or_subscription_dominant(v: str) -> bool:
    if not matches(v, ["chatgpt", "gpt", "openai", "plus"]):
        return False
    if matches(
        v,
        [
            "codex api",
            "api cdk",
            "api 额度",
            "api额度",
            "api中转",
            "api 中转",
            "充值余额",
            "余额充值",
            "中转余额",
            "美元额度",
            "美金额度",
            "刀额度",
        ],
    ):
        return False
    return (
        is_chatgpt_plus(v)
        or is_chatgpt_pro20(v)
        or is_chatgpt_pro5(v)
        or is_chatgpt_free_account(v)
        or is_chatgpt_account_title(v)
    )


_PRO = ["pro", "gpt pro", "chatgpt pro"]


def is_chatgpt_pro20(v: str) -> bool:
    if matches(v, ["gemini", "claude"]):
        return False
    if is_primary_chatgpt_pro5_tier(v):
        return False
    if is_mixed_chatgpt_pro_tier(v):
        return False
    return matches(v, _PRO) and has_chatgpt_pro20_signal(v)


def is_chatgpt_pro5(v: str) -> bool:
    if matches(v, ["gemini", "claude"]):
        return False
    if is_mixed_chatgpt_pro_tier(v):
        return False
    return matches(v, _PRO) and has_chatgpt_pro5_signal(v)


def is_mixed_chatgpt_pro_tier(v: str) -> bool:
    if matches(v, ["gemini", "claude"]):
        return False
    if not matches(v, _PRO):
        return False
    if is_primary_chatgpt_pro5_tier(v):
        return False
    return has_chatgpt_pro5_signal(v) and has_chatgpt_pro20_signal(v)


def is_primary_chatgpt_pro5_tier(v: str) -> bool:
    return test(
        r"\b(?:chatgpt\s*)?(?:gpt\s*)?pro\s*5x\s*(?:月卡|套餐|官方|充值|卡充|直充|代充)", v
    ) or test(
        r"\b(?:chatgpt\s*)?(?:gpt\s*)?pro\s*5\s*倍\s*(?:月卡|套餐|官方|充值|卡充|直充|代充)", v
    )


def has_chatgpt_pro20_signal(v: str) -> bool:
    return (
        matches(v, ["20x", "x20", "20倍", "200刀", "200 美元", "200美元", "200美金", "200 美金"])
        or test(r"200\s*\$", v)
        or test(r"\bpro\s*20\b", v)
    )


def has_chatgpt_pro5_signal(v: str) -> bool:
    return (
        matches(v, ["5x", "x5", "5倍", "100刀", "100 美元", "100美元", "100美金", "100 美金"])
        or test(r"100\s*\$", v)
        or test(r"\bpro\s*5\b", v)
    )


def is_chatgpt_team(v: str) -> bool:
    if matches(v, ["gemini", "claude", "grok"]):
        return False
    if is_chatgpt_team_exclusion(v):
        return False
    return is_chatgpt_team_dominant(v) or matches(v, ["team", "t5", "t5倍", "k12"])


def is_chatgpt_team_dominant(v: str) -> bool:
    if matches(v, ["gemini", "claude", "grok"]):
        return False
    if is_chatgpt_team_exclusion(v):
        return False
    if is_chatgpt_plus_carpool(v):
        return False
    if is_chatgpt_plus_account_with_parent_email(v):
        return False
    if (
        has_email_signal(v)
        and matches(v, ["母号"])
        and not matches(v, ["team", "business", "k12", "团队", "席位", "邀请", "自动拉", "直拉"])
    ):
        return False
    return matches(
        v,
        [
            "gpt team",
            "chatgpt team",
            "k12",
            "k12 子号",
            "team bug",
            "bug team",
            "team子号",
            "team 子号",
            "team账号",
            "team 账号",
            "team成品",
            "team 成品",
            "team席位",
            "team 席位",
            "team反代",
            "team 反代",
            "team月卡",
            "team 月卡",
            "team rt",
            "team凭证",
            "team 凭证",
            "chatgpt business",
            "gpt business",
            "gptbusiness",
            "business(team)",
            "business team",
            "busisness team",
            "business子号",
            "business 子号",
            "团队",
            "母号",
            "自动拉",
            "直拉",
            "拼车位",
            "车位",
            "邀请",
            "团队号",
            "团队席位",
            "席位",
        ],
    )


def is_chatgpt_plus_account_with_parent_email(v: str) -> bool:
    if not matches(v, ["plus"]):
        return False
    if not matches(v, ["成品号", "独享成品号", "独享成品"]):
        return False
    if not matches(v, ["母号邮箱", "母号 邮箱"]):
        return False
    return matches(v, ["icloud", "gmail", "邮箱", "google", "outlook", "hotmail"])


def is_chatgpt_plus_carpool(v: str) -> bool:
    if not matches(v, ["plus", "chatgpt plus", "gpt plus"]):
        return False
    if not matches(v, ["拼车"]):
        return False
    return not matches(v, ["team", "business", "t5", "团队", "母号", "自动拉", "直拉"])


def is_chatgpt_team_exclusion(v: str) -> bool:
    return matches(
        v,
        [
            "有team不能冲",
            "有 team 不能冲",
            "非team",
            "非 team",
            "不是team",
            "不是 team",
            "无team",
            "无 team",
            "不含team",
            "不含 team",
            "要稳买我的team",
            "要稳买我的 team",
        ],
    )


def is_negated_plus(v: str) -> bool:
    if test(r"不是\s*plus\s*的", v):
        return False
    return matches(
        v,
        [
            "非plus",
            "非 plus",
            "不是plus",
            "不是 plus",
            "不含plus",
            "不含 plus",
            "无plus",
            "无 plus",
        ],
    )
