"""Безкоштовна діагностика; скасована заявка без пристрою не вважається відкритою."""
from alembic import op

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

OPEN_WHERE = "status NOT IN ('completed', 'returned') AND NOT (status = 'cancelled' AND device_received_at IS NULL)"


def upgrade():
    # діагностика безкоштовна: послуги з прейскуранту більше не додають суму до кошторису
    op.execute("UPDATE service_catalog SET default_price = 0, warranty_days = 0 WHERE name LIKE 'Діагностика%'")
    # скасовану онлайн-заявку, пристрій якої не надходив, закриваємо датою скасування
    op.execute("""
        UPDATE repair_orders o SET completed_at = COALESCE(o.completed_at, (
            SELECT max(h.changed_at) FROM order_status_history h WHERE h.order_id = o.id AND h.new_status = 'cancelled'), o.updated_at)
        WHERE o.status = 'cancelled' AND o.device_received_at IS NULL
    """)
    op.execute("DROP INDEX IF EXISTS uq_open_order_per_device")
    op.execute(f"""
        DO $$ BEGIN
            CREATE UNIQUE INDEX uq_open_order_per_device ON repair_orders (device_id) WHERE {OPEN_WHERE};
        EXCEPTION WHEN unique_violation THEN
            RAISE WARNING 'TechDesk: на деякі пристрої вже відкрито по дві заявки; індекс не створено';
        END $$
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_open_order_per_device")
    op.execute("""
        DO $$ BEGIN
            CREATE UNIQUE INDEX uq_open_order_per_device ON repair_orders (device_id) WHERE status NOT IN ('completed', 'returned');
        EXCEPTION WHEN unique_violation THEN
            RAISE WARNING 'TechDesk: на деякі пристрої вже відкрито по дві заявки; індекс не створено';
        END $$
    """)
