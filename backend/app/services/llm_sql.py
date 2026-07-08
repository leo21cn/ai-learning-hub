"""LLM 直写 SQL 的 NL2SQL 服务(qwen-plus + dashscope SDK)。

主流程(参见 plan §2.1):
  1. is_enabled():DASHSCOPE_API_KEY 已配置
  2. generate_sql(q, schema_hint):调 dashscope Generation.call 让 qwen-plus 直写 SELECT
  3. validate_sql():7 道闸白名单(_sql_safety.validate_sql)
  4. execute_search_sql():在 read-only 事务中执行,只取 id 列表
     (补齐 CoursewareItem 字段由 search._fetch_coursewares 完成,避免 LLM
     必须 JOIN 出 category/tag/material,降低白名单风险)
  5. search():主入口;失败/超时/校验拒绝 → 返回 ([], 'keyword')
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import _sql_safety

logger = logging.getLogger(__name__)


# ============================================================
# 进程级词汇缓存
# ============================================================
# 背景:为了让 LLM 能识别"用户问的 X 其实是分类名/标签名"(例:用户说"项目实践",
# 但实际是 category.name = '项目实践'),需要在 schema hint 中注入
# 当前数据库里所有的 category.name / tag.name 实际值。
#
# 性能考虑:每次搜索请求多查一次 DB(< 1ms,小表),但 LLM 提示词带表名
# 数量随业务增长。加入进程级缓存(TTL 60s)避免重复查询。
# 后台管理增删分类/标签后最长延迟 60s 后生效,这个 trade-off 可接受。
_VOCAB_CACHE: dict = {}
_VOCAB_LOCK = threading.Lock()
_VOCAB_TTL_SECONDS = 60.0


def _build_vocab_hint(db: Session) -> str:
    """从数据库查询实际的 category.name + tag.name 列表,
    返回一个拼接到 SCHEMA_HINT 末尾的提示字符串,供 LLM 识别
    "用户问的 X 实际是分类/标签名"。

    包含进程级缓存(默认 60s),避免每次请求都查 DB。
    如果查询失败,返回空字符串(优雅降级,不影响主流程)。
    """
    cache_key = "vocab_hint"
    now = time.monotonic()
    with _VOCAB_LOCK:
        cached = _VOCAB_CACHE.get(cache_key)
        if cached and (now - cached["ts"]) < _VOCAB_TTL_SECONDS:
            return cached["value"]

    try:
        cat_names = [
            r[0]
            for r in db.execute(
                text("SELECT name FROM category ORDER BY id")
            ).all()
        ]
        tag_names = [
            r[0]
            for r in db.execute(
                text("SELECT name FROM tag ORDER BY id")
            ).all()
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning("build_vocab_hint failed: %s", e)
        with _VOCAB_LOCK:
            _VOCAB_CACHE[cache_key] = {"ts": now, "value": ""}
        return ""

    # 去重(防御性)+ 过滤空值
    cat_names = [n for n in dict.fromkeys(cat_names) if n]
    tag_names = [n for n in dict.fromkeys(tag_names) if n]

    # 控制长度:避免 prompt 过长
    cat_str = ", ".join(cat_names[:50])  # 上限 50
    tag_str = ", ".join(tag_names[:50])

    hint = ""
    if cat_str:
        hint += f"\n\n## 已知分类名(真实值)\n\n{cat_str}"
    if tag_str:
        hint += f"\n\n## 已知标签名(真实值)\n\n{tag_str}"

    if hint:
        hint += (
            "\n\n**重要**:用户问句中出现的词,如果在以上分类名或标签名中"
            "出现或近似,**必须同时考虑查对应的 category.name / tag.name**(用 ILIKE '%%关键词%%')。"
            "例如用户问'项目实践相关的课件'——'项目实践'在已知分类名中,"
            "应生成 `JOIN category ON c.category_id = cat.id WHERE cat.name ILIKE '%%项目实践%%'`。"
            "如果不确定(如用户问'项目管理'),**也建议同时查 title/description/category.name 三处**,"
            "用 OR 组合,避免漏检。"
        )

    with _VOCAB_LOCK:
        _VOCAB_CACHE[cache_key] = {"ts": now, "value": hint}
    return hint


def invalidate_vocab_cache() -> None:
    """后台管理增删分类/标签后,可调用此函数让 LLM 提示词立即刷新。
    不用调也没事,最多 60s 后自动失效。
    """
    with _VOCAB_LOCK:
        _VOCAB_CACHE.clear()


# ============================================================
# Schema 描述(放在 prompt 中给 qwen-plus 看)
# ============================================================
# 设计原则(见 doc/spec/05-数据模型.md、10-API设计规范 §5.1.3):
# 1. LLM 只需要为"前台自然语言搜索"这一种场景生成 SQL,场景单一
# 2. 搜索的主战场是 courseware.title / description / author,
#    以及 courseware_tag -> tag.name 关联。
#    category.name 是导航分类(如"项目实践"),**不是用户搜索词的语义化对象**。
# 3. 必须用 ILIKE 做子串匹配(中文不依赖分词),不要用 = 精确匹配
#    用户的自然语言输入(例如"项目管理")。
# 4. 所有文本搜索模式必须用 ILIKE '%keyword%' 形式,避免全表扫描不加 WHERE。
SCHEMA_HINT = """\
## 业务背景

Learning Hub 是一个企业学习资料门户。用户在前台搜索框输入自然语言(如"项目管理"、"帮我找一下 Java 入门课件"),
后端将其转为 SQL 查询 courseware 表(前台可搜的课件),返回相关课件卡片。

**核心数据实体**:Courseware(课件)是搜索主对象;Material(素材)只是课件的附件,
当前搜索场景不需要返回素材,但课件可按素材类型过滤。

## 核心搜索表:c courseware (课件)

| 字段            | 类型         | 说明                                                       | 搜索场景适用度 |
|-----------------|--------------|------------------------------------------------------------|----------------|
| `id`            | INT PK       | 主键;**这是 SELECT 必须返回的列**(后续会用 id 补齐详情)     | 必出           |
| `title`         | VARCHAR(100) | 课件标题;**最重要的搜索字段**,用户几乎总在问 title        | ★★★ 最优先   |
| `author`        | VARCHAR(50)  | 作者;次要搜索字段(如"张三讲的")                             | ★★            |
| `description`   | TEXT         | 课件描述;**对长尾问句最重要**——"项目管理相关的课程"常在描述里| ★★            |
| `category_id`   | INT FK       | 指向 category.id;用于按分类筛选,不等同于"按分类名搜索"     | 仅过滤        |
| `access_mode`   | VARCHAR(16)  | 枚举 `'OPEN'` / `'RESTRICTED'`;默认 `'OPEN'`              | 仅过滤        |
| `created_at`    | TIMESTAMPTZ  | 创建时间                                                   | 排序/过滤     |
| `updated_at`    | TIMESTAMPTZ  | 更新时间;**默认按此倒序排列**                                | 排序          |

> 名称近似但语义不同的字段:
> - `title` / `description` 是"软文本",用户问"XX 课"几乎都在这里,用 **ILIKE '%关键词%'**。
> - `category_id` 是外键,不是"用户问的分类名"。**不要**用 `WHERE category_id = (SELECT id FROM category WHERE name = '关键词')`
>   这种查询代替文本匹配。

## 分类表:category (导航用,不是搜索主体)

| 字段         | 类型         | 说明                                              |
|--------------|--------------|---------------------------------------------------|
| `id`         | INT PK       | 主键                                              |
| `name`       | VARCHAR(30)  | 分类名(如"项目实践" "BPO业务" "管理培训");**是导航层级名**,不是用户提问对象 |
| `parent_id`  | INT NULL FK  | 父分类 id;根为 NULL                                |
| `level`      | INT [1,2,3]  | 1=根级, 2=二级, 3=三级                            |

> **重要:user 在搜索框输的"项目管理""Java 入门"等不是 category.name**。
> category.name 是后端管理时设定的导航层级(通常 3-5 个),与用户提问自由文本无关。
> 如果用户表述里出现"分类""目录"等词才考虑查 category.name,否则用 courseware 文本字段。

## 标签表:tag (横向能力 / 主题)

| 字段        | 类型         | 说明                                            |
|-------------|--------------|-------------------------------------------------|
| `id`        | INT PK       | 主键                                            |
| `name`      | VARCHAR(30)  | 标签名(全局唯一,如"敏捷" "Spring");扁平词条     |
| `created_at`| TIMESTAMPTZ  | 创建时间                                        |

> courseware 与 tag 是 M:N,通过 `courseware_tag` 关联。标签常作为"主题词"被用户提及,
> 命中可能性仅次于 title。

## 素材表:material (课件附件,搜索时一般不用)

| 字段                | 类型          | 说明                                                        |
|---------------------|---------------|-------------------------------------------------------------|
| `id`                | INT PK        | 主键                                                        |
| `name`              | VARCHAR(255)  | 原始文件名(可能含中文,如"BPO计件类业务与组织变形.pdf")       |
| `type`              | VARCHAR(16)   | 枚举 `'VIDEO'` / `'PDF'` / `'PPT'`                          |
| `size_bytes`        | BIGINT        | 文件字节数                                                  |
| `duration_or_pages` | VARCHAR(32)   | 视频为时长(12:34), PDF/PPT 为页数                          |
| `storage_path`      | VARCHAR(512)  | 服务端物理路径;**SQL 不要 SELECT 出去**                      |
| `preview_pdf_path`  | VARCHAR(512)  | PPT 转换出的 PDF 路径;NULL=未转换                            |
| `uploaded_at`       | TIMESTAMPTZ   | 上传时间                                                    |

> 当前搜索场景**不需要查询 material 表**——用户搜的是课件,不是素材文件本身。
> 只有当用户明确说"PDF 课件""视频课件"时,才考虑用 `material.type` 过滤:
> `JOIN courseware_material + JOIN material WHERE material.type = 'VIDEO'`。
> 即便如此,应**优先返回 courseware 行**,不要把 material 字段全 SELECT 出去。

## 关联表(用于 JOIN)

- `courseware_tag(courseware_id, tag_id)` M:N
- `courseware_material(courseware_id, material_id)` M:N
- `courseware_access_token(courseware_id, access_token_id)` M:N
  (此表与搜索无关,但 LLM 可能误生成 JOIN,不要碰它)

## 业务规则关键点(来自 doc/spec/05-数据模型.md)

- **R-08** 前台搜索必须返回所有**已发布**的课件;当前 schema 不区分草稿/发布状态,
  但默认所有行都是可搜的。如需限定可加 `WHERE courseware.access_mode = 'OPEN'` 过滤(可选)。
- **R-09** `access_mode = 'RESTRICTED'` 的课件仍可被搜索到(展示在结果中),但下载/浏览时需 token。
  前台搜索不区分 OPEN/RESTRICTED——两条记录都返回。
- **排序** 默认 `ORDER BY courseware.updated_at DESC LIMIT 20`(具体 LIMIT 由调用方传入,上限 50)。
- **可见字段** SELECT 子句里只查:`id, title, author, category_id, description, access_mode, updated_at`。
  禁查 `storage_path` 等敏感字段。
"""


SYSTEM_PROMPT = """\
你是一个 PostgreSQL SQL 生成助手,为 Learning Hub 前台搜索生成单条 SELECT。

## 数据库 schema

{schema}

## 硬性规则(任一违反 = 失败)
1. 只输出单条 SELECT;**禁止** INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/EXEC/COPY/
   VACUUM/SET/RESET/CALL/DO/UNION/INTERSECT/EXCEPT/REVOKE/LOCK/COMMENT 等任何 DDL/DML
2. 必须含 WHERE 子句(避免全表扫描);WHERE 至少有一个对 courseware 文本字段的 ILIKE 过滤
3. 必须显式含 LIMIT(<=50);**默认** `ORDER BY courseware.updated_at DESC LIMIT 20`
4. 只查需要的列:`id, title, author, category_id, description, access_mode, updated_at`;
   禁 `SELECT *`;**禁**查 `storage_path`、`preview_pdf_path` 等敏感/冗余字段
5. 只用 schema 内的表;不允许 `pg_*`、`information_schema`、schema 限定(如 `public.courseware`)
6. 不允许 `;` 多语句;不允许 `--` / `/* */` 注释
7. 不输出 markdown 代码块;不要任何解释;只输出纯 SQL 一行

## 软性规则(强烈推荐,不强制)
- **文本匹配用 ILIKE**,不要用 `=` 或 `==`;用户问的是自然语言,不会精确匹配分类名/标签名
- 用户的问句里几乎都有"找 / 搜索 / 帮我 / 相关的 / 关于"等废话,先**丢弃这类停用词**,
  提取核心名词(名词短语 2-4 字),再用作 ILIKE 关键词。例如:
  - "项目管理相关的课件" -> 关键词 "项目管理"
  - "Java 入门视频" -> 关键词 "Java"、"入门",可 OR 多个 ILIKE
  - "BJC 项目管理及软件工程能力介绍" -> 关键词 "项目管理" / "BJC" / "软件工程"
- 多关键词:用 `AND` 或 `OR` 组合多个 ILIKE;默认 OR(覆盖更广),AND 太严格易 0 命中
- 不需要 JOIN 也能命中大多数情况:把 ILIKE 加在 `courseware.title` 与 `courseware.description` 上即可
- 仅在用户**明确提及**"标签/分类/类型"时,才考虑 JOIN 关联表;否则 1 个表足矣

## 常见错误模式(请避免)
- 错误:用户问"项目管理" → `WHERE category.name = '项目管理'` —— category.name 是导航层级,不是用户问的对象
- 错误:`WHERE title = '项目管理'` —— 标题是自然语言,不会精确匹配
- 错误:`SELECT *` —— 列过多会触发安全闸拒绝
- 错误:不加 LIMIT / 加 LIMIT 100 —— 会触发截断/补 LIMIT 闸

## 正确示例(供你模仿)

用户问:"项目管理"
→ `SELECT id, title, author, category_id, description, access_mode, updated_at FROM courseware WHERE title ILIKE '%项目管理%' OR description ILIKE '%项目管理%' ORDER BY updated_at DESC LIMIT 20`

用户问:"Java 入门"
→ `SELECT id, title, author, category_id, description, access_mode, updated_at FROM courseware WHERE title ILIKE '%Java%' OR title ILIKE '%入门%' OR description ILIKE '%Java%' ORDER BY updated_at DESC LIMIT 20`

用户问:"BJC 视频"
→ `SELECT c.id, c.title, c.author, c.category_id, c.description, c.access_mode, c.updated_at FROM courseware c JOIN courseware_material cm ON c.id = cm.courseware_id JOIN material m ON cm.material_id = m.id WHERE (c.title ILIKE '%BJC%' OR c.title ILIKE '%视频%') AND m.type = 'VIDEO' GROUP BY c.id ORDER BY c.updated_at DESC LIMIT 20`

记住:用户问的是"什么课件",不是"哪个分类",优先在 courseware.title/description 上做 ILIKE。
"""


# ============================================================
# 启用检测
# ============================================================
def is_enabled() -> bool:
    """DASHSCOPE_API_KEY 已配置且非空 → LLM 路径可用。"""
    settings = get_settings()
    return bool(settings.dashscope_api_key and settings.dashscope_api_key.strip())


# ============================================================
# 调 LLM 生成 SQL
# ============================================================
def generate_sql(
    user_query: str,
    *,
    schema_hint: str = SCHEMA_HINT,
    vocab_hint: str = "",
) -> Optional[str]:
    """调 dashscope qwen-plus 生成 SELECT 字符串。

    Args:
        user_query: 原始用户输入(自然语言)
        schema_hint: 表结构描述(可由调用方覆盖,默认使用模块级 SCHEMA_HINT)
        vocab_hint: 动态查询出的 category.name / tag.name 实际值列表,
                    会拼接到 schema_hint 后面。默认空,表示不使用。

    Returns:
        str: LLM 返回的 SQL(可能含 markdown fence / 多余空白 — 由 validate_sql 清洗)。
        None: 超时 / 解析失败 / 返回空 / dashscope 抛错。
    """
    if not user_query or not user_query.strip():
        return None
    settings = get_settings()
    if not is_enabled():
        return None

    try:
        import dashscope  # 局部导入,允许测试时未安装
        from dashscope import Generation
    except Exception as e:  # noqa: BLE001
        logger.warning("dashscope import failed: %s", e)
        return None

    dashscope.api_key = settings.dashscope_api_key
    model = settings.llm_search_model or "qwen-plus"
    timeout_s = float(settings.llm_sql_timeout_seconds or 8.0)

    # 拼接 vocab_hint 到 schema_hint 末尾
    full_schema = schema_hint + (vocab_hint or "")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(schema=full_schema)},
        {"role": "user", "content": user_query.strip()},
    ]

    try:
        resp = Generation.call(
            model=model,
            messages=messages,
            temperature=0.0,
            top_p=0.9,
            result_format="message",
            timeout=timeout_s,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("dashscope Generation.call failed: %s", e)
        return None

    if resp is None or getattr(resp, "output", None) is None:
        logger.warning("dashscope returned empty output")
        return None

    try:
        text_out = resp.output.choices[0].message.content
    except (AttributeError, IndexError, KeyError) as e:
        logger.warning("dashscope response parse error: %s", e)
        return None

    if not text_out or not text_out.strip():
        return None
    return text_out


# ============================================================
# SQL 校验(委托 _sql_safety)
# ============================================================
def validate_sql(
    raw: str, *, default_limit: int = _sql_safety.DEFAULT_LIMIT
) -> Optional[str]:
    """7 道闸校验。失败返回 None。"""
    return _sql_safety.validate_sql(raw, default_limit=default_limit)


# ============================================================
# 提取 id 列(LLM 可能写 id 列别名,如 `AS courseware_id`)
# ============================================================
_ID_COLUMN_RE = re.compile(r"^id$|courseware\.id|\bas\s+id\b", re.IGNORECASE)


def _extract_id_column_name(sql: str) -> str:
    """从 LLM 生成的 SELECT 中找出 id 列的输出名;默认 'id'。"""
    m = re.search(r"SELECT\s+(.+?)\s+FROM\b", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return "id"
    cols = [c.strip() for c in m.group(1).split(",")]
    for col in cols:
        # 形如 `courseware.id` 或 `courseware.id AS foo` 或 `id AS foo`
        head = re.split(r"\s+AS\s+", col, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        alias = (
            re.split(r"\s+AS\s+", col, maxsplit=1, flags=re.IGNORECASE)[1].strip()
            if " AS " in col.upper()
            else head.rsplit(".", 1)[-1].strip("\"`")
        )
        if head.lower().endswith(".id") or head.lower() == "id":
            return alias
    return "id"


# ============================================================
# 执行 SQL(read-only 事务,避免 LLM 意外 DML)
# ============================================================
def execute_search_sql(db: Session, sql: str, *, size: int) -> List[int]:
    """在 read-only 事务中执行 LLM 生成的 SELECT,按 id 列表返回。

    Returns:
        list[int]: 课件 id 列表(按 SQL 输出顺序,可能已被 ORDER BY 排序)。
        list=[]: SQL 抛出 / 无结果。

    注:仅取 id 列,不取其他字段。完整 CoursewareItem 由
    search._fetch_coursewares 补齐(tags/materials/category 等关联)。
    """
    if not sql or not sql.strip():
        return []

    capped_size = max(1, min(int(size), _sql_safety.HARD_LIMIT_CEIL))
    id_col = _extract_id_column_name(sql)

    try:
        # PostgreSQL 的 SET TRANSACTION READ ONLY 必须在事务首条语句前发出
        db.execute(text("SET TRANSACTION READ ONLY"))
        rows = db.execute(text(sql)).all()
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM SQL execution failed: %s", e)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return []

    ids: List[int] = []
    seen: set[int] = set()
    for r in rows:
        # rows 是 Row 对象,支持按列名或索引取;用 id_col 找不到时回退到 0 号列
        val = None
        try:
            val = r._mapping[id_col]  # type: ignore[attr-defined]
        except (AttributeError, KeyError):
            try:
                val = r[0]
            except (IndexError, KeyError):
                continue
        if val is None:
            continue
        try:
            cid = int(val)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
        if len(ids) >= capped_size:
            break
    return ids


# ============================================================
# 主入口(给 search.py 调用)
# ============================================================
def search(
    db: Session, *, keyword: str, size: int = 20
) -> Tuple[List[int], str]:
    """NL2SQL 主入口。

    Returns:
        (ids, source):
            ids: 课件 id 列表(LLM 命中时按 LLM 排序;空时为 [])。
            source: "llm" 成功 / "keyword" 失败(无 key / 超时 / 校验拒绝 / 无结果)。

    调用方拿到 ids 后,应通过 search._fetch_coursewares 补齐完整字段。
    """
    if not keyword or not keyword.strip():
        return [], "keyword"
    if not is_enabled():
        return [], "keyword"

    # 动态注入数据库中实际的 category.name / tag.name 列表,让 LLM 能识别
    # "用户问的 X 其实是分类/标签名" (例: 用户说 "项目实践相关" → 查到 category.name='项目实践')。
    vocab_hint = _build_vocab_hint(db)
    raw = generate_sql(keyword, vocab_hint=vocab_hint)
    if raw is None:
        return [], "keyword"

    settings = get_settings()
    cleaned = validate_sql(
        raw, default_limit=int(size or settings.llm_sql_max_rows or 20)
    )
    if cleaned is None:
        logger.info("LLM SQL rejected by safety check, fallback")
        return [], "keyword"

    ids = execute_search_sql(db, cleaned, size=size)
    if not ids:
        return [], "keyword"
    return ids, "llm"


__all__ = [
    "SCHEMA_HINT",
    "SYSTEM_PROMPT",
    "is_enabled",
    "generate_sql",
    "validate_sql",
    "execute_search_sql",
    "search",
]
