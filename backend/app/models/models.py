"""
Modelos ORM de SQLAlchemy para el Servicio de Inventario del Taller.
Mapean exactamente las 9 tablas de Supabase PostgreSQL.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    BigInteger,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    topic = Column(String(64), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Part(Base):
    __tablename__ = "parts"

    part_id = Column(Integer, primary_key=True)
    sku = Column(String(128), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    family = Column(String(64), nullable=True)
    group_name = Column(String(128), nullable=True)
    subgroup = Column(String(128), nullable=True)
    unit_name = Column(String(32), default="piece")
    image_url = Column(Text, nullable=True)
    active = Column(Boolean, default=True)


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_workbench = Column(Boolean, default=False)
    active = Column(Boolean, default=True)


class BomLine(Base):
    __tablename__ = "bom_lines"

    bom_line_id = Column(Integer, primary_key=True)
    model_id = Column(Integer, nullable=False, index=True)
    part_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    group_name = Column(String(128), nullable=True)
    qty_per_unit = Column(Integer, nullable=True)
    sort_order = Column(Integer, default=0)


class WorkOrder(Base):
    __tablename__ = "work_orders"

    work_order_id = Column(Integer, primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    model_id = Column(Integer, nullable=True)
    department = Column(String(64), nullable=True)
    current_stage = Column(String(64), default="awaiting_quick_inspection")
    is_deleted = Column(Boolean, default=False, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    movement_id = Column(BigInteger, primary_key=True, autoincrement=True)
    part_id = Column(Integer, nullable=False, index=True)
    location_id = Column(Integer, nullable=False, index=True)
    delta = Column(Integer, nullable=False)  # positivo=entrada, negativo=salida
    movement_type = Column(String(32), nullable=False)  # receipt, issue, transfer_out, transfer_in, adjustment
    reference_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id = Column(Integer, primary_key=True, autoincrement=True)
    work_order_id = Column(Integer, nullable=False, index=True)
    bom_line_id = Column(Integer, nullable=True, index=True)
    part_id = Column(Integer, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    status = Column(String(32), default="active", nullable=False)  # active, fulfilled, cancelled
    inspection_item_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Shortage(Base):
    __tablename__ = "shortages"

    shortage_id = Column(Integer, primary_key=True, autoincrement=True)
    work_order_id = Column(Integer, nullable=False, index=True)
    bom_line_id = Column(Integer, nullable=True)
    part_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    missing_quantity = Column(Integer, nullable=True)
    status = Column(String(32), default="open", nullable=False)  # open, resolved, cancelled
    inspection_item_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UnmatchedReceipt(Base):
    __tablename__ = "unmatched_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_line_id = Column(Integer, nullable=False, unique=True)
    part_number = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, nullable=False)
    work_order_code = Column(String(64), nullable=True)
    status = Column(String(32), default="pending", nullable=False)  # pending, resolved
    resolved_part_id = Column(Integer, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
