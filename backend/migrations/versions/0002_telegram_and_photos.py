"""Telegram notifications and device photos"""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('telegram_link_code', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('telegram_link_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('users_telegram_chat_id_key', 'users', ['telegram_chat_id'])
    op.create_unique_constraint('users_telegram_link_code_key', 'users', ['telegram_link_code'])
    op.create_table('device_photos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
    sa.Column('caption', sa.String(length=200), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_device_photos_device_id', 'device_photos', ['device_id'])
    op.create_index('ix_device_photos_order_id', 'device_photos', ['order_id'])

def downgrade():
    op.drop_index('ix_device_photos_order_id', table_name='device_photos')
    op.drop_index('ix_device_photos_device_id', table_name='device_photos')
    op.drop_table('device_photos')
    op.drop_constraint('users_telegram_link_code_key', 'users', type_='unique')
    op.drop_constraint('users_telegram_chat_id_key', 'users', type_='unique')
    op.drop_column('users', 'telegram_link_expires_at')
    op.drop_column('users', 'telegram_link_code')
    op.drop_column('users', 'telegram_chat_id')
