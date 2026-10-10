import asyncio
import sys
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

TEST_SHORTAGE_NAME = "PIEZA DE PRUEBA HACKATEC"
TEST_PURCHASE_ID = 999999

async def insert_test():
    async with AsyncSessionLocal() as session:
        # 1. Insert test shortage with 999 missing units
        await session.execute(text("""
            INSERT INTO shortages (work_order_id, name, missing_quantity, status)
            VALUES (999999, :name, 999, 'open')
        """), {"name": TEST_SHORTAGE_NAME})
        
        # 2. Insert test work order so it shows up in critical orders
        await session.execute(text("""
            INSERT INTO work_orders (work_order_id, code, is_deleted)
            VALUES (999999, 'ORDEN-HACKATEC-TEST', false)
            ON CONFLICT (work_order_id) DO NOTHING
        """))
        
        # 3. Insert test unmatched receipt
        await session.execute(text("""
            INSERT INTO unmatched_receipts (purchase_line_id, part_number, description, quantity, status)
            VALUES (:pid, 'TEST-SKU-999', 'PAQUETE DE PRUEBA HACKATEC (ENCODER 5000 RPM)', 77, 'pending')
            ON CONFLICT (purchase_line_id) DO NOTHING
        """), {"pid": TEST_PURCHASE_ID})
        
        await session.commit()
        print("✅ Registros de prueba insertados con éxito:")
        print("   • Faltante: 'PIEZA DE PRUEBA HACKATEC' (999 unidades)")
        print("   • Orden Crítica: 'ORDEN-HACKATEC-TEST'")
        print("   • Paquete Muelle: 'PAQUETE DE PRUEBA HACKATEC' (77 unidades)")

async def clean_test():
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM shortages WHERE name = :name"), {"name": TEST_SHORTAGE_NAME})
        await session.execute(text("DELETE FROM work_orders WHERE work_order_id = 999999"))
        await session.execute(text("DELETE FROM unmatched_receipts WHERE purchase_line_id = :pid"), {"pid": TEST_PURCHASE_ID})
        await session.commit()
        print("🧹 Registros de prueba eliminados con éxito. Base de datos restaurada.")

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "insert"
    if action == "clean":
        asyncio.run(clean_test())
    else:
        asyncio.run(insert_test())
