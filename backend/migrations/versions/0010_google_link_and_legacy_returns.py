"""Підтверджене пов'язання входу через Google; старі скасовані заявки вважаються повернутими"""
from alembic import op
import sqlalchemy as sa
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('google_linked', sa.Boolean(), nullable=False, server_default=sa.false()))
    # До етапу «Повернуто клієнту» скасування було кінцевим: пристрій віддавали одразу.
    # Без цього всі старі скасовані заявки з'явилися б у вкладці «До видачі».
    op.execute("""
        INSERT INTO order_status_history (order_id, changed_by_id, old_status, new_status, comment, changed_at)
        SELECT id, COALESCE(master_id, client_id), 'cancelled', 'returned',
               'Закрито під час оновлення системи: пристрій повернуто разом зі скасуванням', now()
        FROM repair_orders WHERE status = 'cancelled'
    """)
    op.execute("UPDATE repair_orders SET status = 'returned', completed_at = COALESCE(completed_at, updated_at) "
               "WHERE status = 'cancelled'")

def downgrade():
    op.drop_column('users', 'google_linked')
