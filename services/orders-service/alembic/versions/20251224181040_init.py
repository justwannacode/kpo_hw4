from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251224181040"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    order_status = postgresql.ENUM(
        "NEW",
        "FINISHED",
        "CANCELLED",
        name="order_status",
        create_type=False,
    )
    order_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("status", order_status, nullable=False, server_default="NEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])

    op.create_table(
        "inbox_messages",
        sa.Column("message_id", sa.String(length=128), primary_key=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exchange", sa.String(length=128), nullable=False),
        sa.Column("routing_key", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_published_at", "outbox_messages", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_published_at", table_name="outbox_messages")
    op.drop_table("outbox_messages")
    op.drop_table("inbox_messages")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
    op.execute("DROP TYPE IF EXISTS order_status")
