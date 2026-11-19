"""Відновлення пароля листом: хеш одноразового посилання та строк його дії."""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("reset_token_hash", sa.String(64)))
    op.add_column("users", sa.Column("reset_expires_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_users_reset_token_hash", "users", ["reset_token_hash"])


def downgrade():
    op.drop_constraint("uq_users_reset_token_hash", "users", type_="unique")
    op.drop_column("users", "reset_expires_at")
    op.drop_column("users", "reset_token_hash")
