"""
SQLAlchemy database models for actions.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_polis.shared.db import Base, JSONType

if TYPE_CHECKING:
    from agent_polis.agents.db_models import Agent


class Action(Base):
    """
    Action model - a proposed action awaiting approval.
    
    This is the core entity for impact preview: agents submit actions,
    we generate previews, humans approve/reject, then we execute.
    """
    
    __tablename__ = "actions"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Who proposed this action
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id"),
        nullable=False,
        index=True,
    )
    
    # Action details
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    target: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONType,
        nullable=False,
        default=dict,
    )
    
    context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    
    # Preview (generated after submission)
    preview: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    
    risk_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Approval
    approved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id"),
        nullable=True,
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    modification_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Execution
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    
    execution_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Options
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
    )
    
    auto_approve_if_low_risk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    callback_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
    )
    
    approver: Mapped["Agent | None"] = relationship(
        "Agent",
        foreign_keys=[approved_by],
    )
    
    def __repr__(self) -> str:
        return f"<Action {self.id} ({self.action_type}, {self.status})>"
    
    def is_expired(self) -> bool:
        """Check if this action has expired."""
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        # Handle SQLite which doesn't preserve timezone info
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires
    
    def can_be_approved(self) -> bool:
        """Check if this action can still be approved."""
        return self.status == "pending" and not self.is_expired()
