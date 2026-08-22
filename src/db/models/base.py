"""Lớp cơ sở (declarative base) dùng chung cho toàn bộ model SQLAlchemy.

Theo nguyên tắc tách lớp ở CLAUDE.md mục 2, module `src/db/models/` chỉ định
nghĩa cấu trúc bảng (SQLAlchemy ORM) — KHÔNG chứa logic nghiệp vụ (tính KPI,
RBAC, tính aging_bucket...), logic đó thuộc `src/services/`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Lớp cơ sở cho tất cả model SQLAlchemy của dự án Dashboard LACCO.

    Mọi model trong `src/db/models/` phải kế thừa từ lớp này để cùng chia sẻ
    một registry/metadata — cần thiết để Alembic (bước 2.3) tự động phát
    hiện đầy đủ bảng khi autogenerate migration.
    """
