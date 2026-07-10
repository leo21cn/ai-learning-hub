"""本地开发用：种入最小可工作数据集。

执行后即可访问:
- 1 个课件(分类 → 第3级 / 2 个标签 / 1 个素材 / OPEN 访问)
- 1 个受限课件(同样挂同素材, RESTRICTED + 1 token)
- 1 个 PPT 素材(无预览, fallback 演示)
- 1 个视频素材
- 1 个 PDF 素材
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import Base
from app.models.access_token import AccessToken
from app.models.category import Category
from app.models.courseware import Courseware, AccessMode
from app.models.material import Material, MaterialType
from app.models.tag import Tag
from app.models.association import (
    courseware_access_token,
    courseware_material,
    courseware_tag,
)
from app.services.material import _storage_root


def main() -> None:
    s = get_settings()
    _url = s.effective_database_url
    print(f"[dev-seed] DATABASE_URL={_url}")
    if _url.startswith("sqlite"):
        engine = create_engine(
            _url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(_url)

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    try:
        # 清空旧数据
        db.execute(courseware_material.delete())
        db.execute(courseware_access_token.delete())
        db.execute(courseware_tag.delete())
        db.execute(courseware_access_token.delete())
        db.execute(Courseware.__table__.delete())
        db.execute(Material.__table__.delete())
        db.execute(Category.__table__.delete())
        db.execute(Tag.__table__.delete())
        db.execute(AccessToken.__table__.delete())
        db.commit()

        # 分类 3 级
        cat_a = Category(name="前端开发", level=1, parent_id=None)
        db.add(cat_a)
        db.flush()
        cat_b = Category(name="框架", level=2, parent_id=cat_a.id)
        db.add(cat_b)
        db.flush()
        cat_c = Category(name="Vue", level=3, parent_id=cat_b.id)
        db.add(cat_c)
        db.flush()
        cat_d = Category(name="React", level=3, parent_id=cat_b.id)
        db.add(cat_d)
        db.flush()

        # 标签
        tag_intro = Tag(name="入门")
        tag_adv = Tag(name="进阶")
        db.add_all([tag_intro, tag_adv])
        db.flush()

        # 素材
        # 1) PDF 文件：用 reportlab 生成真实可解析 PDF（2 页含中文）
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # 注册思源黑体 Noto Sans CJK SC（若系统没装则 fallback 到 Helvetica）
        try:
            pdfmetrics.registerFont(TTFont("NotoSC", "C:/Windows/Fonts/msyh.ttc"))
            font_name = "NotoSC"
        except Exception:
            font_name = "Helvetica"

        pdf_path = _storage_root() / "demo-intro.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        c.setFont(font_name, 22)
        c.drawString(80, 760, "Vue 3 入门教程")
        c.setFont(font_name, 12)
        c.drawString(80, 720, "这是 Learning Hub 本地 demo 的 PDF 素材。")
        c.drawString(80, 700, "由 dev_seed.py + reportlab 生成。")
        c.drawString(80, 660, "第 1 页：组合式 API 概念")
        c.drawString(80, 640, "  · setup() / ref() / reactive()")
        c.drawString(80, 620, "  · computed() / watch()")
        c.showPage()
        c.setFont(font_name, 18)
        c.drawString(80, 760, "第 2 页：示例代码")
        c.setFont(font_name, 11)
        c.drawString(80, 720, 'import { ref, computed } from "vue"')
        c.drawString(80, 700, "const count = ref(0)")
        c.drawString(80, 680, "const double = computed(() => count.value * 2)")
        c.save()
        pdf_bytes = pdf_path.read_bytes()
        mat_pdf = Material(
            name="vue-intro.pdf",
            type=MaterialType.PDF.value,
            size_bytes=len(pdf_bytes),
            storage_path=str(pdf_path),
        )
        db.add(mat_pdf)
        db.flush()

        # 2) 视频文件
        video_bytes = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 1024
        video_path = _storage_root() / "demo-hooks.mp4"
        video_path.write_bytes(video_bytes)
        mat_video = Material(
            name="react-hooks.mp4",
            type=MaterialType.VIDEO.value,
            size_bytes=len(video_bytes),
            storage_path=str(video_path),
        )
        db.add(mat_video)
        db.flush()

        # 3) PPT 文件(无预览)
        ppt_bytes = b"PK\x03\x04 fake pptx body"
        ppt_path = _storage_root() / "demo-slides.pptx"
        ppt_path.write_bytes(ppt_bytes)
        mat_ppt = Material(
            name="react-slides.pptx",
            type=MaterialType.PPT.value,
            size_bytes=len(ppt_bytes),
            storage_path=str(ppt_path),
            preview_pdf_path=None,
        )
        db.add(mat_ppt)
        db.flush()

        # Token
        from app.services import access_token as token_svc

        tok_info = token_svc.create(db, label="demo-token")
        raw_token = tok_info["value"]
        tok = db.get(AccessToken, tok_info["id"])
        db.flush()

        # 课件 1: OPEN, Vue 入门
        cw1 = Courseware(
            title="Vue 3 入门教程",
            author="张三",
            description="Vue 3 基础概念与组合式 API。配套 PDF 与示例代码。",
            access_mode=AccessMode.OPEN,
            category_id=cat_c.id,
        )
        cw1.tags = [tag_intro]
        cw1.materials = [mat_pdf]
        cw1.access_tokens = []
        db.add(cw1)
        db.flush()

        # 课件 2: RESTRICTED, React 进阶
        cw2 = Courseware(
            title="React Hooks 进阶",
            author="李四",
            description="深入理解 useState/useEffect 的工作机制,以及自定义 Hook 最佳实践。",
            access_mode=AccessMode.RESTRICTED,
            category_id=cat_d.id,
        )
        cw2.tags = [tag_intro, tag_adv]
        cw2.materials = [mat_video, mat_ppt]
        cw2.access_tokens = [tok]
        db.add(cw2)
        db.flush()
        # v1.5+: 显式写入素材顺序(seed 演示按学习路径排序)。
        # video (sort_order=0) → ppt (sort_order=1)
        for idx, m in enumerate([mat_video, mat_ppt]):
            db.execute(
                courseware_material.update()
                .where(
                    (courseware_material.c.courseware_id == cw2.id)
                    & (courseware_material.c.material_id == m.id)
                )
                .values(sort_order=idx)
            )
        db.flush()

        db.commit()
        print("[dev-seed] inserted:")
        print(f"  - categories: {[c.name for c in db.query(Category).all()]}")
        print(f"  - tags: {[t.name for t in db.query(Tag).all()]}")
        print(f"  - materials: {[(m.name, m.type) for m in db.query(Material).all()]}")
        print(f"  - access tokens (raw): {raw_token}")
        print(f"  - coursewares: {[(c.id, c.title, c.access_mode.value) for c in db.query(Courseware).all()]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
