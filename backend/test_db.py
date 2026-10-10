"""
Script de demostración y verificación de salud de la Base de Datos.
Ejecutar con:
    .venv\\Scripts\\python test_db.py
"""

import asyncio
import sys

# Asegurar codificación UTF-8 en consolas Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from app.core.database import engine

REQUIRED_TABLES = [
    "processed_events",
    "parts",
    "locations",
    "bom_lines",
    "work_orders",
    "inventory_movements",
    "reservations",
    "shortages",
    "unmatched_receipts",
]

async def verify_system():
    print("\n" + "=" * 60)
    print("   VERIFICACION OFICIAL DE BASE DE DATOS (PERSONA 2)")
    print("   Hackathon HackaTecNM - Almacen Inteligente")
    print("=" * 60 + "\n")

    print("[1/3] Conectando a Supabase PostgreSQL...")
    try:
        async with engine.connect() as conn:
            # 1. Versión de PostgreSQL
            version_res = await conn.execute(text("SELECT version();"))
            pg_version = version_res.scalar()
            print("      [OK] Conexion establecida con exito!")
            print(f"      [INFO] Motor: {pg_version.split(',')[0]}\n")

            # 2. Verificar tablas
            print("[2/3] Verificando las 9 tablas requeridas por el contrato:")
            tables_res = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            )
            existing_tables = set(r[0] for r in tables_res.fetchall())

            all_ok = True
            for tbl in REQUIRED_TABLES:
                if tbl in existing_tables:
                    print(f"      [OK] {tbl:<25} -> LISTA Y ACTIVA")
                else:
                    print(f"      [FALTA] {tbl:<25} -> NO ENCONTRADA")
                    all_ok = False

            # 3. Resultado final
            print("\n[3/3] Diagnostico:")
            if all_ok:
                print("      >>> ESTADO: 100% OPERATIVO Y SINCRONIZADO <<<")
                print("      Todas las 9 tablas requeridas por el contrato estan activas.")
            else:
                print("      >>> ESTADO: FALTAN ALGUNAS TABLAS <<<")

    except Exception as e:
        print(f"\n[ERROR] Fallo la conexion: {e}")

    print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(verify_system())
