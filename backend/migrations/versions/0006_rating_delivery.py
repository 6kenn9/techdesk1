from alembic import op
import sqlalchemy as sa
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('repair_orders', sa.Column('rating', sa.SmallInteger(), nullable=True))
    op.add_column('repair_orders', sa.Column('rating_comment', sa.Text(), nullable=False, server_default=''))
    op.add_column('repair_orders', sa.Column('rated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('repair_orders', sa.Column('delivery_method', sa.String(length=15), nullable=False, server_default='pickup'))
    op.add_column('repair_orders', sa.Column('delivery_city', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('repair_orders', sa.Column('delivery_branch', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('repair_orders', sa.Column('delivery_ttn', sa.String(length=14), nullable=True))
    op.create_check_constraint('valid_rating', 'repair_orders', 'rating IS NULL OR rating BETWEEN 1 AND 5')
    op.create_check_constraint('valid_delivery', 'repair_orders', "delivery_method IN ('pickup', 'nova_poshta')")

def downgrade():
    op.drop_constraint('valid_delivery', 'repair_orders', type_='check')
    op.drop_constraint('valid_rating', 'repair_orders', type_='check')
    for column in ('delivery_ttn', 'delivery_branch', 'delivery_city', 'delivery_method', 'rated_at', 'rating_comment', 'rating'):
        op.drop_column('repair_orders', column)
