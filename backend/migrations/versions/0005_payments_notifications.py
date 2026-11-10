"""Payments with method and in-app notifications for staff"""
from alembic import op
import sqlalchemy as sa
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('repair_orders.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('amount > 0', name='positive_payment'),
        sa.CheckConstraint("method IN ('cash', 'card', 'transfer')", name='valid_payment_method'))
    op.create_index('ix_payments_order_id', 'payments', ['order_id'])
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('repair_orders.id'), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('text', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    # Наявні оплати переносимо як готівкові, щоб суми в заявках і нові записи збігалися.
    op.execute("""
        INSERT INTO payments (order_id, amount, method, note, created_by_id, created_at)
        SELECT o.id, o.paid_amount, 'cash', 'Перенесено з попередньої версії',
               COALESCE(o.master_id, (SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1)),
               COALESCE(o.completed_at, o.updated_at)
        FROM repair_orders o WHERE o.paid_amount > 0
    """)

def downgrade():
    op.drop_index('ix_notifications_user_id', 'notifications')
    op.drop_table('notifications')
    op.drop_index('ix_payments_order_id', 'payments')
    op.drop_table('payments')
