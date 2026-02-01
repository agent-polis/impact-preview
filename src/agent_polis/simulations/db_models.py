"""
SQLAlchemy database models for simulations.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_polis.shared.db import Base, JSONType

if TYPE_CHECKING:
    from agent_polis.agents.db_models import Agent


class Simulation(Base):
    """
    Simulation model - a scenario execution in the sandbox.
    
    Simulations are the core value proposition: test proposals/plans
    before committing to them.
    """
    
    __tablename__ = "simulations"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Creator
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id"),
        nullable=False,
        index=True,
    )
    
    # Optional link to proposal (for governance integration)
    proposal_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )  # pending, running, completed, failed, canceled
    
    # Scenario definition
    scenario_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONType,
        nullable=False,
    )
    
    # Execution details
    e2b_sandbox_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Results
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    
    # Predictions and actuals for tracking accuracy
    predicted_outcome: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    
    actual_outcome: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType,
        nullable=True,
    )
    
    # Webhook callback URL
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
    
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    creator: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="simulations",
    )
    
    def __repr__(self) -> str:
        return f"<Simulation {self.id} ({self.status})>"
