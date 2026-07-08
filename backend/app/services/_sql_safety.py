"""SQL 白名单校验:LLM 生成 raw SQL 后必经的 7 道闸。

设计目标(参见 plan §2.3):
  - LLM 生成的 SELECT 必须通过纯函数校验,方可进入执行层。
  - 任一道闸失败 → 返回 None(由调用方 fallback 到关键词 ILIKE)。
  - 校验逻辑不依赖数据库,便于 pytest 直接覆盖。

7 道闸依次为:
  1. 去 markdown 代码块包裹
  2. 单语句(去末尾分号;中间不允许 `;`)
  3. 无注释(`--` / `/*` / `*/`)
  4. 首词必须为 SELECT
  5. 黑名单关键字(整词匹配)
  6. FROM/JOIN 中的表必须在白名单内
  7. 强制 LIMIT(缺失则追加;显式 LIMIT > max_rows 截断)
"""
from __future__ import annotations

import re
from typing import Optional, Set


# 业务允许的表(主表 + 关联表)
ALLOWED_TABLES: Set[str] = {
    "courseware",
    "category",
    "tag",
    "material",
    "courseware_tag",
    "courseware_material",
    "courseware_access_token",
}

# 系统表 / 隐藏 schema 一律拒绝
DISALLOWED_TABLE_PREFIXES: tuple[str, ...] = (
    "pg_",
    "information_schema",
    "pg_catalog",
    "pg_toast",
)

# 黑名单关键字(整词匹配);UNION/INTERSECT/EXCEPT 也会绕过白名单表检查
BLACKLIST_KEYWORDS: Set[str] = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "COPY",
    "VACUUM",
    "LOCK",
    "COMMENT",
    "SET",
    "RESET",
    "CALL",
    "DO",
    "UNION",
    "INTERSECT",
    "EXCEPT",
}

# 7 道闸的硬上限
HARD_LIMIT_CEIL = 50
DEFAULT_LIMIT = 20


# 预编译正则
_FENCE_RE = re.compile(r"^\s*```(?:sql)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)
_COMMENT_LINE_RE = re.compile(r"--")
_COMMENT_BLOCK_RE = re.compile(r"/\*|\*/")
_SELECT_FIRST_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_TRAILING_SEMI_RE = re.compile(r";\s*$")
_INTERNAL_SEMI_RE = re.compile(r";")
_FROM_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([\"`\[]?\w+[\"`\]]?)(?:\s+(?:AS\s+)?(\w+))?",
    re.IGNORECASE,
)
_BLACKLIST_RE = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in BLACKLIST_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_markdown_fence(raw: str) -> str:
    """闸 1:去除 ```sql ... ``` 或 ``` ... ``` 包裹。"""
    text = raw.strip()
    # 多步去 fence:开头一行 + 末尾一行
    text = re.sub(r"^\s*```(?:sql)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    # 兜底:整段被单行 fence 包围(无换行)
    text = re.sub(r"^\s*```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _strip_trailing_semi(text: str) -> str:
    """闸 2 辅助:去掉末尾一个 `;`。"""
    return _TRAILING_SEMI_RE.sub("", text).rstrip()


def _check_single_statement(text: str) -> bool:
    """闸 2:不允许中间存在 `;`(多语句)。"""
    return not _INTERNAL_SEMI_RE.search(text)


def _check_no_comments(text: str) -> bool:
    """闸 3:不允许 `--` 行注释或 `/* */` 块注释。"""
    if _COMMENT_LINE_RE.search(text):
        return False
    if _COMMENT_BLOCK_RE.search(text):
        return False
    return True


def _check_select_first(text: str) -> bool:
    """闸 4:首词必须为 SELECT。"""
    return bool(_SELECT_FIRST_RE.match(text))


def _check_blacklist(text: str) -> bool:
    """闸 5:整词匹配黑名单关键字(大小写不敏感)。"""
    return _BLACKLIST_RE.search(text) is None


def _check_tables(text: str) -> bool:
    """闸 6:从 FROM / JOIN 提取的表必须在白名单,且不含系统表前缀。"""
    for match in _FROM_JOIN_RE.finditer(text):
        raw_ident = match.group(1)
        # 去引号 / 反引号 / 方括号
        ident = raw_ident.strip("\"'`[]")
        if not ident:
            return False
        # 拒绝 schema-qualified 形式(防止 user 拉跨 schema)
        if "." in ident:
            return False
        ident_l = ident.lower()
        if ident_l in DISALLOWED_TABLE_PREFIXES:
            return False
        for prefix in DISALLOWED_TABLE_PREFIXES:
            if ident_l.startswith(prefix):
                return False
        if ident_l not in ALLOWED_TABLES:
            return False
    return True


def _enforce_limit(text: str, default_limit: int) -> str:
    """闸 7:缺失 LIMIT → 追加;显式 LIMIT > HARD_LIMIT_CEIL → 截断。"""
    m = _LIMIT_RE.search(text)
    if m is None:
        return f"{text.rstrip()} LIMIT {int(default_limit)}"
    val = int(m.group(1))
    if val > HARD_LIMIT_CEIL:
        return _LIMIT_RE.sub(f"LIMIT {HARD_LIMIT_CEIL}", text, count=1)
    return text


def validate_sql(raw: str, *, default_limit: int = DEFAULT_LIMIT) -> Optional[str]:
    """7 道闸校验;通过 → 返回清洗后的 SQL,失败 → 返回 None。

    Args:
        raw: LLM 原始输出(可能含 markdown fence / 注释 / 多余空白)。
        default_limit: 缺 LIMIT 时使用的兜底值(<= HARD_LIMIT_CEIL)。

    Returns:
        str: 清洗后可安全执行的 SELECT。
        None: 任一闸失败,调用方应 fallback。
    """
    if not raw or not raw.strip():
        return None

    # 闸 1:去 markdown fence
    text = _strip_markdown_fence(raw)
    if not text:
        return None

    # 闸 2:单语句
    text = _strip_trailing_semi(text)
    if not _check_single_statement(text):
        return None

    # 闸 3:无注释
    if not _check_no_comments(text):
        return None

    # 闸 4:首词 SELECT
    if not _check_select_first(text):
        return None

    # 闸 5:黑名单关键字
    if not _check_blacklist(text):
        return None

    # 闸 6:表白名单
    if not _check_tables(text):
        return None

    # 闸 7:强制 LIMIT
    safe_default = max(1, min(int(default_limit), HARD_LIMIT_CEIL))
    text = _enforce_limit(text, safe_default)

    # 规范化空白
    return _WHITESPACE_RE.sub(" ", text).strip()


__all__ = [
    "ALLOWED_TABLES",
    "BLACKLIST_KEYWORDS",
    "DEFAULT_LIMIT",
    "HARD_LIMIT_CEIL",
    "validate_sql",
]
