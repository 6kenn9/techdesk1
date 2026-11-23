from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repair_orders", sa.Column("device_received_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE repair_orders SET device_received_at = created_at")


def downgrade():
    op.drop_column("repair_orders", "device_received_at")
