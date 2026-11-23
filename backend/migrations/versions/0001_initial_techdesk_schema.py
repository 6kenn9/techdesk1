from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('device_model_presets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_category', sa.String(length=40), nullable=False),
    sa.Column('brand', sa.String(length=80), nullable=False),
    sa.Column('model_name', sa.String(length=120), nullable=False),
    sa.Column('default_specs', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('typical_defects', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('device_category', 'brand', 'model_name')
    )
    op.create_table('service_catalog',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=False),
    sa.Column('default_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('estimated_hours', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('warranty_days', sa.Integer(), nullable=False),
    sa.CheckConstraint('default_price >= 0 AND estimated_hours >= 0 AND warranty_days >= 0', name='valid_service'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('spare_parts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=False),
    sa.Column('compatible_device_category', sa.String(length=40), nullable=False),
    sa.Column('quantity_in_stock', sa.Integer(), nullable=False),
    sa.Column('min_stock_level', sa.Integer(), nullable=False),
    sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('sale_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('spec_upgrade_target', sa.String(length=80), nullable=False),
    sa.Column('spec_upgrade_value', sa.String(length=160), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity_in_stock >= 0 AND min_stock_level >= 0 AND cost_price >= 0 AND sale_price >= 0', name='valid_inventory'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=24), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('specialization', sa.String(length=180), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('client','master','admin')", name='valid_role'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('phone')
    )
    op.create_table('devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('serial_number', sa.String(length=80), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('device_category', sa.String(length=40), nullable=False),
    sa.Column('brand', sa.String(length=80), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('specifications', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('cosmetic_condition', sa.Text(), nullable=False),
    sa.Column('known_defects_history', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_owner_id'), 'devices', ['owner_id'], unique=False)
    op.create_index(op.f('ix_devices_serial_number'), 'devices', ['serial_number'], unique=True)
    op.create_table('repair_orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_number', sa.String(length=32), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('master_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('problem_description', sa.Text(), nullable=False),
    sa.Column('completeness', sa.Text(), nullable=False),
    sa.Column('cosmetic_notes', sa.Text(), nullable=False),
    sa.Column('diagnostics', sa.Text(), nullable=False),
    sa.Column('internal_notes', sa.Text(), nullable=False),
    sa.Column('is_warranty_case', sa.Boolean(), nullable=False),
    sa.Column('works_total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('parts_total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_cost', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('approved_total', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('client_approval_status', sa.String(length=15), nullable=False),
    sa.Column('approval_comment', sa.Text(), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('warranty_days', sa.Integer(), nullable=False),
    sa.Column('warranty_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("client_approval_status IN ('pending','approved','rejected')", name='valid_approval'),
    sa.CheckConstraint("status IN ('registered','diagnostics','waiting_approval','in_repair','ready_for_pickup','completed','cancelled')", name='valid_status'),
    sa.CheckConstraint('warranty_days >= 0 AND paid_amount >= 0', name='valid_order_amounts'),
    sa.ForeignKeyConstraint(['client_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['master_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_number')
    )
    op.create_index(op.f('ix_repair_orders_client_id'), 'repair_orders', ['client_id'], unique=False)
    op.create_index(op.f('ix_repair_orders_device_id'), 'repair_orders', ['device_id'], unique=False)
    op.create_index(op.f('ix_repair_orders_master_id'), 'repair_orders', ['master_id'], unique=False)
    op.create_index(op.f('ix_repair_orders_status'), 'repair_orders', ['status'], unique=False)
    op.create_table('device_spec_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('changed_by_id', sa.Integer(), nullable=False),
    sa.Column('field_name', sa.String(length=80), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=False),
    sa.Column('new_value', sa.Text(), nullable=False),
    sa.Column('change_reason', sa.Text(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_spec_history_device_id'), 'device_spec_history', ['device_id'], unique=False)
    op.create_table('inventory_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('part_id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('change_amount', sa.Integer(), nullable=False),
    sa.Column('stock_after', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=180), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('stock_after >= 0 AND change_amount != 0', name='valid_movement'),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.ForeignKeyConstraint(['part_id'], ['spare_parts.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_transactions_part_id'), 'inventory_transactions', ['part_id'], unique=False)
    op.create_table('order_parts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('part_id', sa.Integer(), nullable=False),
    sa.Column('part_name', sa.String(length=160), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_cost_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unit_sale_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_sale_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('spec_upgrade_target', sa.String(length=80), nullable=False),
    sa.Column('spec_upgrade_value', sa.String(length=160), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity > 0 AND unit_cost_price >= 0 AND unit_sale_price >= 0', name='valid_order_part'),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.ForeignKeyConstraint(['part_id'], ['spare_parts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_parts_order_id'), 'order_parts', ['order_id'], unique=False)
    op.create_table('order_status_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('changed_by_id', sa.Integer(), nullable=False),
    sa.Column('old_status', sa.String(length=30), nullable=True),
    sa.Column('new_status', sa.String(length=30), nullable=False),
    sa.Column('comment', sa.Text(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_status_history_order_id'), 'order_status_history', ['order_id'], unique=False)
    op.create_table('order_works',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=True),
    sa.Column('work_name', sa.String(length=160), nullable=False),
    sa.Column('master_id', sa.Integer(), nullable=True),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('updates_passport_spec', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('price >= 0', name='nonnegative_work_price'),
    sa.ForeignKeyConstraint(['master_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['repair_orders.id'], ),
    sa.ForeignKeyConstraint(['service_id'], ['service_catalog.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_works_order_id'), 'order_works', ['order_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_order_works_order_id'), table_name='order_works')
    op.drop_table('order_works')
    op.drop_index(op.f('ix_order_status_history_order_id'), table_name='order_status_history')
    op.drop_table('order_status_history')
    op.drop_index(op.f('ix_order_parts_order_id'), table_name='order_parts')
    op.drop_table('order_parts')
    op.drop_index(op.f('ix_inventory_transactions_part_id'), table_name='inventory_transactions')
    op.drop_table('inventory_transactions')
    op.drop_index(op.f('ix_device_spec_history_device_id'), table_name='device_spec_history')
    op.drop_table('device_spec_history')
    op.drop_index(op.f('ix_repair_orders_status'), table_name='repair_orders')
    op.drop_index(op.f('ix_repair_orders_master_id'), table_name='repair_orders')
    op.drop_index(op.f('ix_repair_orders_device_id'), table_name='repair_orders')
    op.drop_index(op.f('ix_repair_orders_client_id'), table_name='repair_orders')
    op.drop_table('repair_orders')
    op.drop_index(op.f('ix_devices_serial_number'), table_name='devices')
    op.drop_index(op.f('ix_devices_owner_id'), table_name='devices')
    op.drop_table('devices')
    op.drop_table('users')
    op.drop_table('spare_parts')
    op.drop_table('service_catalog')
    op.drop_table('device_model_presets')
