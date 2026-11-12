"""Етап «Повернуто клієнту» та позначка гарантійного звернення клієнта"""
from alembic import op
import sqlalchemy as sa
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

OLD = "status IN ('registered','diagnostics','waiting_approval','in_repair','ready_for_pickup','completed','cancelled')"
NEW = "status IN ('registered','diagnostics','waiting_approval','in_repair','ready_for_pickup','completed','cancelled','returned')"

def upgrade():
    op.drop_constraint('valid_status', 'repair_orders', type_='check')
    op.create_check_constraint('valid_status', 'repair_orders', NEW)
    op.add_column('repair_orders', sa.Column('warranty_claim', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('repair_orders', 'warranty_claim')
    # повернуті заявки в старій схемі можна показати лише як скасовані
    op.execute("UPDATE repair_orders SET status = 'cancelled' WHERE status = 'returned'")
    op.drop_constraint('valid_status', 'repair_orders', type_='check')
    op.create_check_constraint('valid_status', 'repair_orders', OLD)
