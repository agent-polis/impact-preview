"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Events table (append-only, tamper-evident)
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stream_id', sa.String(255), nullable=False),
        sa.Column('stream_version', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hash', sa.String(64), nullable=False),
        sa.Column('prev_hash', sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stream_id', 'stream_version', name='uq_stream_version'),
    )
    op.create_index('idx_events_stream_version', 'events', ['stream_id', 'stream_version'])
    op.create_index('idx_events_type', 'events', ['event_type'])
    op.create_index('idx_events_created_at', 'events', ['created_at'])

    # Trigger to prevent event modification
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_event_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Events are immutable and cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER events_immutable
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION prevent_event_modification();
    """)

    # Agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('api_key_hash', sa.String(64), nullable=False),
        sa.Column('reputation_score', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verification_method', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('simulations_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('month_reset_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agents_name', 'agents', ['name'], unique=True)
    op.create_index('ix_agents_api_key_hash', 'agents', ['api_key_hash'], unique=True)
    op.create_index('ix_agents_status', 'agents', ['status'])

    # Simulations table
    op.create_table(
        'simulations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('proposal_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('scenario_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('e2b_sandbox_id', sa.String(255), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('predicted_outcome', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('actual_outcome', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('callback_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_simulations_creator_id', 'simulations', ['creator_id'])
    op.create_index('ix_simulations_proposal_id', 'simulations', ['proposal_id'])
    op.create_index('ix_simulations_status', 'simulations', ['status'])


def downgrade() -> None:
    op.drop_table('simulations')
    op.drop_table('agents')

    op.execute("DROP TRIGGER IF EXISTS events_immutable ON events")
    op.execute("DROP FUNCTION IF EXISTS prevent_event_modification()")

    op.drop_table('events')
