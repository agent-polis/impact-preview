"""
SQLAlchemy database models for agents.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_polis.shared.db import Base

if TYPE_CHECKING:
    from agent_polis.simulations.db_models import Simulation


class Agent(Base):
    """
    Agent model - represents a registered AI agent in the polis.
    
    Agents are identified by their API key and have reputation scores
    based on their governance participation and simulation accuracy.
    """
    
    __tablename__ = "agents"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Authentication
    api_key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Reputation and status
    reputation_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    verification_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )  # pending, active, suspended, banned
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Metering
    simulations_this_month: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    month_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    simulations: Mapped[list["Simulation"]] = relationship(
        "Simulation",
        back_populates="creator",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.status})>"
    
    def update_last_active(self) -> None:
        """Update last active timestamp."""
        self.last_active_at = datetime.now(timezone.utc)
    
    def increment_simulation_count(self) -> None:
        """Increment the monthly simulation counter."""
        # Reset if new month
        now = datetime.now(timezone.utc)
        if self.month_reset_at.month != now.month or self.month_reset_at.year != now.year:
            self.simulations_this_month = 0
            self.month_reset_at = now
        self.simulations_this_month += 1
    
    def can_run_simulation(self, monthly_limit: int) -> bool:
        """Check if agent can run another simulation this month."""
        # Reset if new month
        now = datetime.now(timezone.utc)
        if self.month_reset_at.month != now.month or self.month_reset_at.year != now.year:
            return True
        return self.simulations_this_month < monthly_limit
