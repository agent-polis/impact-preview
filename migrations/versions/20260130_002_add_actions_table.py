"""Add actions table for impact preview

Revision ID: 002
Revises: 001
Create Date: 2026-01-30

This migration adds the actions table for the v0.2 pivot to
impact preview. Actions represent proposed operations that need
human approval before execution.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: str | None = '001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Actions table - proposed actions awaiting approval
    op.create_table(
        'actions',
        # Identity
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Action details
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('target', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('context', sa.Text(), nullable=True),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),

        # Preview/analysis results
        sa.Column('preview', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),

        # Approval
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('modification_comment', sa.Text(), nullable=True),

        # Execution
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_error', sa.Text(), nullable=True),

        # Options
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('auto_approve_if_low_risk', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('callback_url', sa.String(500), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for common queries
    op.create_index('ix_actions_agent_id', 'actions', ['agent_id'])
    op.create_index('ix_actions_status', 'actions', ['status'])
    op.create_index('ix_actions_action_type', 'actions', ['action_type'])
    op.create_index('ix_actions_created_at', 'actions', ['created_at'])
    op.create_index('ix_actions_expires_at', 'actions', ['expires_at'])

    # Index for finding pending actions efficiently
    op.create_index(
        'ix_actions_pending',
        'actions',
        ['status', 'created_at'],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index('ix_actions_pending')
    op.drop_index('ix_actions_expires_at')
    op.drop_index('ix_actions_created_at')
    op.drop_index('ix_actions_action_type')
    op.drop_index('ix_actions_status')
    op.drop_index('ix_actions_agent_id')
    op.drop_table('actions')
