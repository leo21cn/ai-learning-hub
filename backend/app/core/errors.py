"""业务错误码与异常类型。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException


class ErrorCode:
    """业务错误码常量集中地,与 [10-API §3.2](../spec/10-API设计规范.md) 一一对应。"""

    # 通用 / 认证
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    MISSING_TOKEN = "missing_token"
    INVALID_ADMIN_TOKEN = "invalid_admin_token"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"

    # 课件
    COURSEWARE_NOT_FOUND = "courseware_not_found"
    COURSEWARE_TITLE_REQUIRED = "courseware_title_required"
    COURSEWARE_CATEGORY_REQUIRED = "courseware_category_required"
    COURSEWARE_CATEGORY_NOT_LEAF = "courseware_category_not_leaf"
    COURSEWARE_TOKEN_REQUIRED = "courseware_token_required"
    COURSEWARE_ACL_LOCKED = "courseware_acl_locked"
    COURSEWARE_HAS_MATERIALS = "courseware_has_materials"
    COURSEWARE_PUBLISH_CONFLICT = "courseware_publish_conflict"
    COURSEWARE_MATERIALS_INVALID = "courseware_materials_invalid"

    # 分类
    CATEGORY_NOT_FOUND = "category_not_found"
    CATEGORY_NAME_REQUIRED = "category_name_required"
    CATEGORY_NAME_CONFLICT = "category_name_conflict"
    CATEGORY_MAX_LEVEL = "category_max_level"
    CATEGORY_HAS_CHILDREN = "category_has_children"
    CATEGORY_HAS_COURSEWARES = "category_has_coursewares"

    # 标签
    TAG_NOT_FOUND = "tag_not_found"
    TAG_NAME_REQUIRED = "tag_name_required"
    TAG_NAME_CONFLICT = "tag_name_conflict"

    # 素材
    MATERIAL_NOT_FOUND = "material_not_found"
    MATERIAL_EXTENSION_INVALID = "material_extension_invalid"
    MATERIAL_SIZE_EXCEEDED = "material_size_exceeded"
    MATERIAL_STORAGE_UNAVAILABLE = "material_storage_unavailable"
    MATERIAL_REFERENCED = "material_referenced"
    MATERIAL_UPLOAD_FAILED = "material_upload_failed"

    # 访问令牌
    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_LABEL_REQUIRED = "token_label_required"
    TOKEN_LABEL_TOO_LONG = "token_label_too_long"
    TOKEN_LABEL_CONFLICT = "token_label_conflict"
    INVALID_TOKEN = "invalid_token"
    INVALID_TOKEN_FORMAT = "invalid_token_format"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_REQUIRED = "token_required"
    LAST_TOKEN_REQUIRED = "last_token_required"
    TOKEN_REFERENCED = "token_referenced"

    # AI 搜索
    SEARCH_QUERY_EMPTY = "search_query_empty"
    SEARCH_QUERY_TOO_LONG = "search_query_too_long"
    LLM_TIMEOUT = "llm_timeout"
    LLM_UNAVAILABLE = "llm_unavailable"
    SEARCH_NO_RESULT = "search_no_result"


_HTTP_BY_CODE: Dict[str, int] = {
    # 通用
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.MISSING_TOKEN: 400,
    ErrorCode.INVALID_ADMIN_TOKEN: 401,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    # 课件
    ErrorCode.COURSEWARE_NOT_FOUND: 404,
    ErrorCode.COURSEWARE_TITLE_REQUIRED: 400,
    ErrorCode.COURSEWARE_CATEGORY_REQUIRED: 400,
    ErrorCode.COURSEWARE_CATEGORY_NOT_LEAF: 400,
    ErrorCode.COURSEWARE_TOKEN_REQUIRED: 400,
    ErrorCode.COURSEWARE_ACL_LOCKED: 403,
    ErrorCode.COURSEWARE_HAS_MATERIALS: 422,
    ErrorCode.COURSEWARE_PUBLISH_CONFLICT: 409,
    ErrorCode.COURSEWARE_MATERIALS_INVALID: 400,
    # 分类
    ErrorCode.CATEGORY_NOT_FOUND: 404,
    ErrorCode.CATEGORY_NAME_REQUIRED: 400,
    ErrorCode.CATEGORY_NAME_CONFLICT: 409,
    ErrorCode.CATEGORY_MAX_LEVEL: 409,
    ErrorCode.CATEGORY_HAS_CHILDREN: 422,
    ErrorCode.CATEGORY_HAS_COURSEWARES: 422,
    # 标签
    ErrorCode.TAG_NOT_FOUND: 404,
    ErrorCode.TAG_NAME_REQUIRED: 400,
    ErrorCode.TAG_NAME_CONFLICT: 409,
    # 素材
    ErrorCode.MATERIAL_NOT_FOUND: 404,
    ErrorCode.MATERIAL_EXTENSION_INVALID: 400,
    ErrorCode.MATERIAL_SIZE_EXCEEDED: 413,
    ErrorCode.MATERIAL_STORAGE_UNAVAILABLE: 500,
    ErrorCode.MATERIAL_REFERENCED: 422,
    ErrorCode.MATERIAL_UPLOAD_FAILED: 500,
    # Token
    ErrorCode.TOKEN_NOT_FOUND: 404,
    ErrorCode.TOKEN_LABEL_REQUIRED: 400,
    ErrorCode.TOKEN_LABEL_TOO_LONG: 400,
    ErrorCode.TOKEN_LABEL_CONFLICT: 409,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.INVALID_TOKEN_FORMAT: 400,
    ErrorCode.TOKEN_REVOKED: 410,
    ErrorCode.TOKEN_REQUIRED: 401,
    ErrorCode.LAST_TOKEN_REQUIRED: 422,
    ErrorCode.TOKEN_REFERENCED: 422,
    # 搜索 / LLM
    ErrorCode.SEARCH_QUERY_EMPTY: 400,
    ErrorCode.SEARCH_QUERY_TOO_LONG: 400,
    ErrorCode.LLM_TIMEOUT: 504,
    ErrorCode.LLM_UNAVAILABLE: 503,
    ErrorCode.SEARCH_NO_RESULT: 200,
}


class BusinessError(HTTPException):
    """业务异常:用业务码 + message 触发统一 JSON 信封响应。"""

    def __init__(self, code: str, message: Optional[str] = None, data: Any = None) -> None:
        status_code = _HTTP_BY_CODE.get(code, 400)
        # 注意:把 code + message + data 塞进 HTTPException 的 detail,
        # 由全局错误处理器重新包装到 {code, message, data, requestId} 信封中。
        super().__init__(status_code=status_code, detail={"code": code, "message": message or code, "data": data})
        self.code = code
        self.message = message or code
        self.payload = data


__all__ = ["BusinessError", "ErrorCode"]
