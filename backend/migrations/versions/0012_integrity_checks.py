"""Правила цілісності в самій базі: суми, етапи, доставка, одна відкрита заявка на пристрій;
оплати без запису в журналі отримують запис, щоб «оплачено» збігалося з таблицею payments."""
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

STATUSES = "('registered','diagnostics','waiting_approval','in_repair','ready_for_pickup','completed','cancelled','returned')"
CHECKS = [
    ("repair_orders", "valid_priority", "priority IN ('normal', 'urgent')"),
    ("repair_orders", "nonnegative_totals", "works_total >= 0 AND parts_total >= 0 AND (approved_total IS NULL OR approved_total >= 0)"),
    ("repair_orders", "consistent_total", "total_cost = CASE WHEN is_warranty_case THEN 0 ELSE works_total + parts_total END"),
    ("repair_orders", "closed_has_date", "status NOT IN ('completed', 'returned') OR completed_at IS NOT NULL"),
    ("repair_orders", "rating_after_completion", "rating IS NULL OR status = 'completed'"),
    ("repair_orders", "shipping_address", "delivery_method <> 'nova_poshta' OR (delivery_city <> '' AND delivery_branch <> '')"),
    ("order_status_history", "valid_new_status", f"new_status IN {STATUSES}"),
    ("order_status_history", "valid_old_status", f"old_status IS NULL OR old_status IN {STATUSES}"),
    ("order_parts", "consistent_part_total", "total_sale_price = quantity * unit_sale_price"),
]


def upgrade():
    # Демодані та старі заявки мали «оплачено» без запису в журналі оплат: додаємо запис на різницю.
    op.execute("""
        INSERT INTO payments (order_id, amount, method, note, created_by_id, created_at)
        SELECT o.id, o.paid_amount - COALESCE(p.total, 0), 'cash', 'Оплату внесено до запуску журналу оплат',
               COALESCE(o.master_id, (SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1), o.client_id),
               COALESCE(o.completed_at, o.updated_at)
        FROM repair_orders o
        LEFT JOIN (SELECT order_id, SUM(amount) AS total FROM payments GROUP BY order_id) p ON p.order_id = o.id
        WHERE o.paid_amount > COALESCE(p.total, 0)
    """)
    # NOT VALID: правило діє для всіх нових змін одразу; наявні рядки перевіряються окремо,
    # і якщо якийсь старий запис його порушує, оновлення бази не зупиняється (буде лише повідомлення в журналі).
    for table, name, rule in CHECKS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({rule}) NOT VALID")
        op.execute(f"""
            DO $$ BEGIN
                ALTER TABLE {table} VALIDATE CONSTRAINT {name};
            EXCEPTION WHEN check_violation THEN
                RAISE WARNING 'TechDesk: наявні записи {table} порушують правило {name}; нові зміни воно вже перевіряє';
            END $$
        """)
    op.execute("""
        DO $$ BEGIN
            CREATE UNIQUE INDEX uq_open_order_per_device ON repair_orders (device_id)
                WHERE status NOT IN ('completed', 'returned');
        EXCEPTION WHEN unique_violation THEN
            RAISE WARNING 'TechDesk: на деякі пристрої вже відкрито по дві заявки; індекс не створено';
        END $$
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_open_order_per_device")
    for table, name, _ in reversed(CHECKS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    op.execute("DELETE FROM payments WHERE note = 'Оплату внесено до запуску журналу оплат'")
