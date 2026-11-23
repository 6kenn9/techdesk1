from alembic import op
import sqlalchemy as sa
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('repair_orders', sa.Column('approved_items', sa.String(length=64), nullable=True))

def downgrade():
    op.drop_column('repair_orders', 'approved_items')
