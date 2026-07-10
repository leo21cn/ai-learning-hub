"""数据模型集合:集中导入,供 Alembic 一次性识别所有 metadata。"""
from app.db import Base
from app.models.category import Category
from app.models.tag import Tag
from app.models.material import Material, MaterialType, infer_type
from app.models.courseware import Courseware, AccessMode
from app.models.access_token import AccessToken
from app.models.access_session import AccessSession
from app.models.association import (
    courseware_tag,
    courseware_material,
    courseware_access_token,
)

__all__ = [
    "Base",
    "Category",
    "Tag",
    "Material",
    "MaterialType",
    "infer_type",
    "Courseware",
    "AccessMode",
    "AccessToken",
    "AccessSession",
    "courseware_tag",
    "courseware_material",
    "courseware_access_token",
]
