"""一次性脚本:为已有 PPT 素材用 LibreOffice + pdftoppm 生成多张 PNG 预览,并落库 preview_images_dir。

用法:
    docker cp regen_ppt_images.py lh-backend:/tmp/regen.py
    docker exec lh-backend python /tmp/regen.py
"""
import os
import shutil
import sys

sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.material import Material
from app.services import ppt_to_images

s = get_settings()
engine = create_engine(s.database_url)
Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
db = Session()

updated = 0
failed = 0
for m in db.query(Material).filter(Material.type == "PPT").all():
    src = m.storage_path
    # 如果已有 preview_images_dir 且有 page-*.png 就不再生成
    if (
        m.preview_images_dir
        and os.path.isdir(m.preview_images_dir)
        and any(
            p.startswith("page-") and p.endswith(".png")
            for p in os.listdir(m.preview_images_dir)
        )
    ):
        print(f"[skip] id={m.id} already has PNGs in {m.preview_images_dir}")
        continue
    if not os.path.exists(src):
        print(f"[fail] id={m.id} source not found: {src}")
        failed += 1
        continue
    print(f"[run] id={m.id} {src}")
    result = ppt_to_images.convert(src, timeout=180)
    if result is None:
        print("  -> convert FAILED")
        failed += 1
        continue
    images_dir, page_count = result
    m.preview_images_dir = str(images_dir)
    m.duration_or_pages = str(page_count)
    db.commit()
    print(f"  -> preview_images_dir={images_dir} pages={page_count}")
    updated += 1

print(f"\nDONE updated={updated} failed={failed}")
