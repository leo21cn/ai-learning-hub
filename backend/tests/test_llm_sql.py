"""LLM 直写 SQL 的安全校验(_sql_safety.validate_sql)单测。

覆盖 7 道闸(无需数据库):
  1. 去 markdown 代码块包裹
  2. 单语句
  3. 无注释
  4. 首词 SELECT
  5. 黑名单关键字
  6. 表白名单
  7. 强制 LIMIT
"""
from __future__ import annotations

import pytest

from app.services import _sql_safety


# ===== 闸 1 / 4 / 7:安全 SELECT 通过 =====

def test_validate_passes_safe_select():
    """最基本的安全 SELECT 应通过,且补全 LIMIT。"""
    sql = "SELECT id, title FROM courseware WHERE title ILIKE '%x%'"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is not None
    assert out.upper().startswith("SELECT")
    assert "LIMIT 20" in out.upper()


def test_validate_appends_default_limit():
    """缺 LIMIT 时自动追加。"""
    sql = "SELECT id FROM courseware"
    out = _sql_safety.validate_sql(sql, default_limit=15)
    assert out is not None
    assert "LIMIT 15" in out.upper()


def test_validate_caps_explicit_limit_to_ceiling():
    """显式 LIMIT > HARD_LIMIT_CEIL(50) → 截断到 50。"""
    sql = "SELECT id FROM courseware LIMIT 200"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is not None
    assert "LIMIT 50" in out.upper()


# ===== 闸 1:markdown fence =====

def test_validate_strips_markdown_fences():
    """被 ```sql ... ``` 包裹的 SQL 应剥离 fence。"""
    raw = "```sql\nSELECT id FROM courseware WHERE title ILIKE '%y%'\n```"
    out = _sql_safety.validate_sql(raw, default_limit=20)
    assert out is not None
    assert "```" not in out
    assert out.upper().startswith("SELECT")


# ===== 闸 2:多语句拒绝 =====

def test_validate_rejects_multiple_statements():
    """含 `;` 多语句应拒绝。"""
    sql = "SELECT 1; DROP TABLE courseware"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


# ===== 闸 3:注释拒绝 =====

def test_validate_rejects_line_comments():
    """`--` 行注释应拒绝。"""
    sql = "SELECT 1 -- comment"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


def test_validate_rejects_block_comments():
    """`/* */` 块注释应拒绝。"""
    sql = "SELECT 1 /* hidden */ FROM courseware"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


# ===== 闸 4:首词 SELECT =====

def test_validate_rejects_non_select_first_word():
    """EXPLAIN / WITH / 其他开头应拒绝。"""
    sql = "EXPLAIN SELECT id FROM courseware"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None

    sql_with = "WITH t AS (SELECT 1) SELECT * FROM t"
    out_with = _sql_safety.validate_sql(sql_with, default_limit=20)
    # WITH 是合法 SELECT 形式;只要通过白名单,允许
    # 但我们这里 t 是伪表,会被闸 6 拦截
    assert out_with is None


# ===== 闸 5:黑名单关键字 =====

@pytest.mark.parametrize(
    "kw",
    ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE",
     "GRANT", "EXEC", "COPY", "VACUUM", "UNION", "INTERSECT", "EXCEPT"],
)
def test_validate_rejects_dml_keywords(kw: str):
    """黑名单关键字(整词)应拒绝。"""
    sql = f"SELECT id FROM courseware WHERE title = '{kw} anything'"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    # 整词匹配:`UPDATE` 在 SELECT 主体里仍会被识别
    assert out is None


def test_validate_rejects_set_keyword():
    """SET 是黑名单关键字,即使包在 SELECT 内也应拒绝。"""
    sql = "SELECT id FROM courseware SET TITLE = 'x'"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    # SET 是黑名单;整词匹配
    assert out is None


# ===== 闸 6:表白名单 =====

def test_validate_rejects_unknown_table():
    """未知表应拒绝。"""
    sql = "SELECT * FROM secret_table"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


def test_validate_rejects_system_table():
    """系统表(pg_user)应拒绝。"""
    sql = "SELECT * FROM pg_user"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


def test_validate_rejects_information_schema():
    """information_schema 应拒绝。"""
    sql = "SELECT * FROM information_schema.tables"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


def test_validate_rejects_schema_qualified():
    """schema.table 限定形式应拒绝(防止拉跨 schema)。"""
    sql = "SELECT id FROM public.courseware"
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None


def test_validate_allows_association_tables():
    """3 张关联表(courseware_tag / courseware_material / courseware_access_token)均应在白名单。"""
    for tbl in ("courseware_tag", "courseware_material", "courseware_access_token"):
        sql = f"SELECT courseware_id FROM {tbl}"
        out = _sql_safety.validate_sql(sql, default_limit=20)
        assert out is not None, f"{tbl} should be allowed"
        assert "LIMIT" in out.upper()


def test_validate_allows_join_with_allowed_tables():
    """含 JOIN 的合法组合应通过。"""
    sql = (
        "SELECT c.id, c.title FROM courseware c "
        "JOIN courseware_tag ct ON ct.courseware_id = c.id "
        "WHERE c.title ILIKE '%管理%'"
    )
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is not None


# ===== 边界 =====

def test_validate_rejects_empty_input():
    """空字符串 / None 应拒绝。"""
    assert _sql_safety.validate_sql("", default_limit=20) is None
    assert _sql_safety.validate_sql("   \n\t  ", default_limit=20) is None
    assert _sql_safety.validate_sql(None, default_limit=20) is None  # type: ignore[arg-type]


def test_validate_case_insensitive():
    """关键字大小写不敏感。"""
    sql_lower = "select id from courseware where id = 1"
    out = _sql_safety.validate_sql(sql_lower, default_limit=20)
    assert out is not None
    assert out.upper().startswith("SELECT")


def test_validate_lowercases_keyword_match_for_blacklist():
    """黑名单大小写不敏感 — `drop`、`Drop` 同样拒绝。"""
    sql = "SELECT id FROM courseware WHERE id = (select 1) drop table x"
    # 多语句 → 闸 2 拒绝(分号)
    out = _sql_safety.validate_sql(sql, default_limit=20)
    assert out is None
