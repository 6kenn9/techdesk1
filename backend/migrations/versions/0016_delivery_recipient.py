"""Інший отримувач посилки Новою Поштою: ім'я та телефон (порожні, якщо отримує сам клієнт)."""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repair_orders", sa.Column("delivery_recipient_name", sa.String(150), nullable=False, server_default=""))
    op.add_column("repair_orders", sa.Column("delivery_recipient_phone", sa.String(20), nullable=False, server_default=""))
    op.create_check_constraint("recipient_pair", "repair_orders",
                               "(delivery_recipient_name = '') = (delivery_recipient_phone = '')")


def downgrade():
    op.drop_constraint("recipient_pair", "repair_orders", type_="check")
    op.drop_column("repair_orders", "delivery_recipient_phone")
    op.drop_column("repair_orders", "delivery_recipient_name")
