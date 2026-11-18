from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。表结构只由 Alembic 迁移创建，禁止代码里建表。"""
