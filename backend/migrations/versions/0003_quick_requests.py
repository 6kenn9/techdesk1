from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('users', 'email', existing_type=sa.String(length=254), nullable=True)
    op.alter_column('devices', 'serial_number', existing_type=sa.String(length=80), nullable=True)
    op.add_column('users', sa.Column('claim_token_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('claim_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('users_claim_token_hash_key', 'users', ['claim_token_hash'])

def downgrade():
    op.drop_constraint('users_claim_token_hash_key', 'users', type_='unique')
    op.drop_column('users', 'claim_expires_at')
    op.drop_column('users', 'claim_token_hash')
    op.execute("UPDATE devices SET serial_number = 'NO-SN-' || id WHERE serial_number IS NULL")
    op.execute("UPDATE users SET email = 'guest-' || id || '@guest.invalid' WHERE email IS NULL")
    op.alter_column('devices', 'serial_number', existing_type=sa.String(length=80), nullable=False)
    op.alter_column('users', 'email', existing_type=sa.String(length=254), nullable=False)
