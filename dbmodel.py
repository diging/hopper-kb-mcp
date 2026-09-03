from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func

from pgvector.sqlalchemy import Vector

from typing import List
from enum import Enum
import datetime



DOCUMENT_TYPES = [
    ("WEBSITE", "website"),
    ("PDF", "pdf"),
    ("DOC", "doc"),
    ("CSV", "csv")
]

DocumentTypes = Enum("DocumentTypes", DOCUMENT_TYPES)

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, nullable=True)
    local_path: Mapped[str] = mapped_column(String, nullable=True)
    doc_type: Mapped[str] = mapped_column(String)
    metadata_json = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=datetime.datetime.now
    )
    modified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=datetime.datetime.now
    )

    chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    
    order_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_vector = mapped_column(Vector(384))  # dimension depends on the model used
    metadata_json = mapped_column(JSON)

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    document: Mapped["Document"] = relationship(back_populates="chunks")