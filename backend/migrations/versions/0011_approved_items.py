"""Відбиток погодженого складу кошторису: зміна позицій після згоди клієнта потребує нового погодження"""
from alembic import op
import sqlalchemy as sa
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade():
    # Для наявних заявок відбиток порожній: для них діє попереднє правило (порівняння суми).
    op.add_column('repair_orders', sa.Column('approved_items', sa.String(length=64), nullable=True))

def downgrade():
    op.drop_column('repair_orders', 'approved_items')
