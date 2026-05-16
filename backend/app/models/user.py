"""User model — stores auth info and connector tokens."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # GitLab OAuth tokens (encrypted in production)
    gitlab_user_id: Mapped[int | None] = mapped_column(nullable=True)
    gitlab_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="owner")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
