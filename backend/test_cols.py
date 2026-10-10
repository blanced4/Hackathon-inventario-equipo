import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        for t in ['parts', 'locations', 'bom_lines', 'work_orders', 'inventory_movements', 'reservations', 'shortages', 'unmatched_receipts', 'processed_events']:
            res = await session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{t}'"))
            cols = [r[0] for r in res.fetchall()]
            print(f"Table {t}: {cols}")

asyncio.run(check())
