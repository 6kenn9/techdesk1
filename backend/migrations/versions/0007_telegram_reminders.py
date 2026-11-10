"""Позначки надісланих нагадувань про кінець гарантії та планову профілактику"""
from alembic import op
import sqlalchemy as sa
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('repair_orders', sa.Column('warranty_reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('repair_orders', sa.Column('maintenance_reminded_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('repair_orders', 'maintenance_reminded_at')
    op.drop_column('repair_orders', 'warranty_reminded_at')
