"""
Procesador central de eventos Kafka para el Servicio de Inventario.
Garantiza:
  1. Idempotencia total mediante tabla processed_events.
  2. Kardex inmutable en inventory_movements (solo INSERTs con delta y movement_type).
  3. Control estricto de concurrencia y saldos no negativos.
  4. Publicación en inventory.events con esquemas y llaves oficiales.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    BomLine,
    InventoryMovement,
    Location,
    Part,
    ProcessedEvent,
    Reservation,
    Shortage,
    UnmatchedReceipt,
    WorkOrder,
)
from app.services import kafka_producer

logger = logging.getLogger(__name__)


async def is_processed(event_id: str, db: AsyncSession) -> bool:
    """Verifica si el evento ya fue procesado para garantizar idempotencia."""
    q = await db.execute(select(ProcessedEvent).where(ProcessedEvent.event_id == str(event_id)))
    return q.scalar_one_or_none() is not None


async def mark_processed(event_id: str, event_type: str, topic: str, db: AsyncSession) -> None:
    """Registra el event_id en processed_events."""
    pe = ProcessedEvent(event_id=str(event_id), event_type=event_type, topic=topic)
    db.add(pe)


async def process_event(event: dict[str, Any], topic: str, db: AsyncSession) -> None:
    """
    Despacha y procesa un evento Kafka deduplicado.
    """
    event_id = str(event.get("event_id"))
    event_type = event.get("event_type", "")
    data = event.get("data", {})

    if not event_id or not event_type:
        return

    # 1. Chequeo de idempotencia
    if await is_processed(event_id, db):
        logger.debug("Evento ya procesado (duplicado ignorado): %s", event_id)
        return

    # 2. Despachar según tópico y tipo
    try:
        if topic == "shop.catalog":
            await _handle_catalog_event(event_type, data, db)
        elif topic == "shop.work_orders":
            await _handle_work_orders_event(event_type, data, db)
        elif topic == "shop.inspections":
            await _handle_inspections_event(event_type, data, db)
        elif topic == "shop.purchasing":
            await _handle_purchasing_event(event_type, data, db)

        # 3. Marcar como procesado y commitear
        await mark_processed(event_id, event_type, topic, db)
        await db.commit()
        logger.info("Procesado con éxito evento %s (%s) en %s", event_type, event_id, topic)

    except Exception as exc:
        await db.rollback()
        logger.error("Error al procesar evento %s (%s): %s", event_type, event_id, exc, exc_info=True)
        raise exc


def _extract_str(val: Any, default: Optional[str] = None) -> Optional[str]:
    if isinstance(val, dict):
        return val.get("name") or val.get("code") or val.get("title") or default
    if val is not None:
        s = str(val).strip()
        return s if s else default
    return default


# ── TÓPICO: shop.catalog ──────────────────────────────────────────────────────

async def _handle_catalog_event(event_type: str, data: dict[str, Any], db: AsyncSession) -> None:
    if event_type == "part.upserted":
        part_id = data["part_id"]
        q = await db.execute(select(Part).where(Part.part_id == part_id))
        part = q.scalar_one_or_none()

        family_str = _extract_str(data.get("family"))
        group_str = _extract_str(data.get("group") or data.get("group_name"))
        subgroup_str = _extract_str(data.get("subgroup"))
        unit_str = _extract_str(data.get("unit"), default="PIEZA") or "PIEZA"

        if not part:
            part = Part(
                part_id=part_id,
                sku=data.get("sku"),
                name=data.get("name", ""),
                family=family_str,
                group_name=group_str,
                subgroup=subgroup_str,
                unit_name=unit_str,
                image_url=data.get("image_url"),
                active=data.get("active", True),
            )
            db.add(part)
        else:
            part.sku = data.get("sku", part.sku)
            part.name = data.get("name", part.name)
            part.family = family_str or part.family
            part.group_name = group_str or part.group_name
            part.subgroup = subgroup_str or part.subgroup
            part.unit_name = unit_str or part.unit_name
            part.image_url = data.get("image_url", part.image_url)
            part.active = data.get("active", part.active)

    elif event_type == "location.upserted":
        location_id = data["location_id"]
        q = await db.execute(select(Location).where(Location.location_id == location_id))
        loc = q.scalar_one_or_none()
        if not loc:
            loc = Location(
                location_id=location_id,
                code=data.get("code", f"U-{location_id:03d}"),
                name=data.get("name", ""),
                is_workbench=data.get("is_workbench", False),
                active=data.get("active", True),
            )
            db.add(loc)
        else:
            loc.code = data.get("code", loc.code)
            loc.name = data.get("name", loc.name)
            loc.is_workbench = data.get("is_workbench", loc.is_workbench)
            loc.active = data.get("active", loc.active)

    elif event_type == "bom.upserted":
        model_id = data.get("model_id")
        lines = data.get("lines", [])
        for line in lines:
            bom_line_id = line["bom_line_id"]
            q = await db.execute(select(BomLine).where(BomLine.bom_line_id == bom_line_id))
            bl = q.scalar_one_or_none()
            if not bl:
                bl = BomLine(
                    bom_line_id=bom_line_id,
                    model_id=model_id,
                    part_id=line.get("part_id"),
                    name=line.get("name", ""),
                    group_name=line.get("group_name"),
                    qty_per_unit=int(line.get("qty_per_unit") or 1),
                    sort_order=int(line.get("sort_order") or 0),
                )
                db.add(bl)
            else:
                bl.model_id = model_id
                bl.part_id = line.get("part_id", bl.part_id)
                bl.name = line.get("name", bl.name)
                bl.group_name = line.get("group_name", bl.group_name)
                bl.qty_per_unit = int(line.get("qty_per_unit") or bl.qty_per_unit)
                bl.sort_order = int(line.get("sort_order") or bl.sort_order)


# ── TÓPICO: shop.work_orders ──────────────────────────────────────────────────

async def _handle_work_orders_event(event_type: str, data: dict[str, Any], db: AsyncSession) -> None:
    wo_id = data.get("work_order_id")
    if not wo_id:
        return

    q = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == wo_id))
    wo = q.scalar_one_or_none()

    if event_type == "work_order.opened":
        if not wo:
            rec_at = None
            if data.get("received_at"):
                try:
                    rec_at = datetime.fromisoformat(data["received_at"].replace("Z", "+00:00"))
                except Exception:
                    rec_at = datetime.now(timezone.utc)
            wo = WorkOrder(
                work_order_id=wo_id,
                code=data["code"],
                model_id=data.get("model_id"),
                department=data.get("department"),
                current_stage="awaiting_quick_inspection",
                received_at=rec_at,
                is_deleted=False,
            )
            db.add(wo)
        else:
            wo.code = data.get("code", wo.code)
            wo.model_id = data.get("model_id", wo.model_id)
            wo.department = data.get("department", wo.department)
            wo.is_deleted = False

    elif event_type == "work_order.stage_changed":
        if wo:
            wo.current_stage = data.get("to_stage", wo.current_stage)

    elif event_type == "work_order.deleted":
        if wo:
            wo.is_deleted = True
        # Regla de baja de orden: cancelar reservas y faltantes abiertos
        await db.execute(
            update(Reservation)
            .where(Reservation.work_order_id == wo_id, Reservation.status == "active")
            .values(status="cancelled")
        )
        await db.execute(
            update(Shortage)
            .where(Shortage.work_order_id == wo_id, Shortage.status == "open")
            .values(status="cancelled")
        )


# ── TÓPICO: shop.inspections ──────────────────────────────────────────────────

async def _handle_inspections_event(event_type: str, data: dict[str, Any], db: AsyncSession) -> None:
    wo_id = data.get("work_order_id")
    if not wo_id:
        return

    q_wo = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == wo_id))
    wo = q_wo.scalar_one_or_none()
    wo_code = wo.code if wo else f"WO-{wo_id}"

    if event_type == "inspection.approved":
        items = data.get("items", [])
        if not items:
            return

        for it in items:
            inspection_item_id = it.get("inspection_item_id")
            bom_line_id = it.get("bom_line_id")
            part_id = it.get("part_id")
            name = it.get("name", "")
            condition = it.get("condition")
            action = it.get("action")

            # Regla: Si quantity es None, tomar qty_per_unit del catálogo
            quantity_val = it.get("quantity")
            if quantity_val is not None:
                quantity = int(quantity_val)
            elif bom_line_id:
                bl_q = await db.execute(select(BomLine).where(BomLine.bom_line_id == bom_line_id))
                bl = bl_q.scalar_one_or_none()
                quantity = int(bl.qty_per_unit) if (bl and bl.qty_per_unit) else 1
            else:
                quantity = 1

            # Regla de reemplazo de necesidades: si llega una nueva inspección con esta línea,
            # reemplaza las reservas activas y faltantes abiertos existentes de esa línea
            if bom_line_id:
                await db.execute(
                    update(Reservation)
                    .where(
                        Reservation.work_order_id == wo_id,
                        Reservation.bom_line_id == bom_line_id,
                        Reservation.status == "active",
                    )
                    .values(status="superseded")
                )
                await db.execute(
                    update(Shortage)
                    .where(
                        Shortage.work_order_id == wo_id,
                        Shortage.bom_line_id == bom_line_id,
                        Shortage.status == "open",
                    )
                    .values(status="superseded")
                )
                await db.flush()
            elif part_id:
                await db.execute(
                    update(Reservation)
                    .where(
                        Reservation.work_order_id == wo_id,
                        Reservation.part_id == part_id,
                        Reservation.status == "active",
                    )
                    .values(status="superseded")
                )
                await db.execute(
                    update(Shortage)
                    .where(
                        Shortage.work_order_id == wo_id,
                        Shortage.part_id == part_id,
                        Shortage.status == "open",
                    )
                    .values(status="superseded")
                )
                await db.flush()

            # Regla oficial: Solo se reserva si requiere compra/reemplazo (action == 'buy' o dañado/faltante)
            if condition == "ok" or action == "repair":
                continue

            # Si la pieza no tiene part_id identificado en catálogo
            if not part_id:
                shortage = Shortage(
                    work_order_id=wo_id,
                    bom_line_id=bom_line_id,
                    part_id=None,
                    name=name,
                    missing_quantity=quantity,
                    inspection_item_id=inspection_item_id,
                    status="open",
                )
                db.add(shortage)
                await db.flush()

                await kafka_producer.publish(
                    "stock.shortage_detected",
                    data={
                        "work_order_id": wo_id,
                        "part_id": None,
                        "name": name,
                        "missing_quantity": quantity,
                        "inspection_item_id": inspection_item_id,
                    },
                    key=wo_code,
                )
                continue

            # Pieza identificada: Calcular disponibilidad real usando delta
            stk_q = await db.execute(
                select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
                    InventoryMovement.part_id == part_id
                )
            )
            on_hand = stk_q.scalar() or 0

            res_q = await db.execute(
                select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
                    Reservation.part_id == part_id,
                    Reservation.status == "active",
                )
            )
            total_reserved = res_q.scalar() or 0

            available = max(0, on_hand - total_reserved)

            if available >= quantity:
                # Stock suficiente: Reserva completa
                res = Reservation(
                    work_order_id=wo_id,
                    bom_line_id=bom_line_id,
                    part_id=part_id,
                    quantity=quantity,
                    inspection_item_id=inspection_item_id,
                    status="active",
                )
                db.add(res)
                await db.flush()

                await kafka_producer.publish(
                    "stock.reserved",
                    data={
                        "reservation_id": res.reservation_id,
                        "work_order_id": wo_id,
                        "part_id": part_id,
                        "quantity": quantity,
                        "inspection_item_id": inspection_item_id,
                    },
                    key=wo_code,
                )
            elif available > 0:
                # Stock parcial: Reserva disponible y crea faltante para el resto
                res_qty = int(available)
                miss_qty = int(quantity - res_qty)

                res = Reservation(
                    work_order_id=wo_id,
                    bom_line_id=bom_line_id,
                    part_id=part_id,
                    quantity=res_qty,
                    inspection_item_id=inspection_item_id,
                    status="active",
                )
                db.add(res)

                shortage = Shortage(
                    work_order_id=wo_id,
                    bom_line_id=bom_line_id,
                    part_id=part_id,
                    name=name,
                    missing_quantity=miss_qty,
                    inspection_item_id=inspection_item_id,
                    status="open",
                )
                db.add(shortage)
                await db.flush()

                await kafka_producer.publish(
                    "stock.reserved",
                    data={
                        "reservation_id": res.reservation_id,
                        "work_order_id": wo_id,
                        "part_id": part_id,
                        "quantity": res_qty,
                        "inspection_item_id": inspection_item_id,
                    },
                    key=wo_code,
                )
                await kafka_producer.publish(
                    "stock.shortage_detected",
                    data={
                        "work_order_id": wo_id,
                        "part_id": part_id,
                        "name": name,
                        "missing_quantity": miss_qty,
                        "inspection_item_id": inspection_item_id,
                    },
                    key=wo_code,
                )
                await kafka_producer.publish(
                    "stock.reorder_suggested",
                    data={
                        "part_id": part_id,
                        "suggested_quantity": miss_qty,
                        "work_order_ids": [wo_id],
                    },
                    key=f"part:{part_id}",
                )
            else:
                # Sin stock disponible: Faltante completo
                miss_qty = int(quantity)
                shortage = Shortage(
                    work_order_id=wo_id,
                    bom_line_id=bom_line_id,
                    part_id=part_id,
                    name=name,
                    missing_quantity=miss_qty,
                    inspection_item_id=inspection_item_id,
                    status="open",
                )
                db.add(shortage)
                await db.flush()

                await kafka_producer.publish(
                    "stock.shortage_detected",
                    data={
                        "work_order_id": wo_id,
                        "part_id": part_id,
                        "name": name,
                        "missing_quantity": miss_qty,
                        "inspection_item_id": inspection_item_id,
                    },
                    key=wo_code,
                )
                await kafka_producer.publish(
                    "stock.reorder_suggested",
                    data={
                        "part_id": part_id,
                        "suggested_quantity": miss_qty,
                        "work_order_ids": [wo_id],
                    },
                    key=f"part:{part_id}",
                )

    elif event_type in ("inspection.rejected", "inspection.voided", "inspection.discarded"):
        # Regla: anular reservas e inspecciones
        items = data.get("items", [])
        item_ids = [it.get("inspection_item_id") for it in items if it.get("inspection_item_id")]
        if item_ids:
            await db.execute(
                update(Reservation)
                .where(Reservation.inspection_item_id.in_(item_ids), Reservation.status == "active")
                .values(status="cancelled")
            )
            await db.execute(
                update(Shortage)
                .where(Shortage.inspection_item_id.in_(item_ids), Shortage.status == "open")
                .values(status="cancelled")
            )
        else:
            await db.execute(
                update(Reservation)
                .where(Reservation.work_order_id == wo_id, Reservation.status == "active")
                .values(status="cancelled")
            )
            await db.execute(
                update(Shortage)
                .where(Shortage.work_order_id == wo_id, Shortage.status == "open")
                .values(status="cancelled")
            )


# ── TÓPICO: shop.purchasing ───────────────────────────────────────────────────

async def _handle_purchasing_event(event_type: str, data: dict[str, Any], db: AsyncSession) -> None:
    if event_type != "purchase.item_received":
        return

    purpose = data.get("purpose")
    # Regla oficial: Compras para cliente directo NO entran a almacén ni emiten stock.received
    if purpose == "customer_order":
        logger.info("Compra para cliente directo (customer_order), omitida de almacén: %s", data.get("line_id"))
        return

    line_id = data["line_id"]
    part_number = data.get("part_number", "").strip()
    description = data.get("description", "")
    quantity = int(data.get("quantity", 0))
    unit_price = data.get("unit_price")
    currency = data.get("currency") or "MXN"
    work_order_code = data.get("work_order_code")

    # Breve ventana para asegurar que eventos de catálogo enviados en el mismo instante se persistan primero
    await asyncio.sleep(0.3)

    # Buscar pieza en el catálogo por SKU (insensible a mayúsculas y espacios según contrato)
    clean_sku = part_number.strip().upper()
    p_q = await db.execute(
        select(Part)
        .where(func.upper(func.trim(Part.sku)) == clean_sku)
    )
    matching_parts = p_q.scalars().all()

    if len(matching_parts) == 0:
        # Breve espera para absorber desorden de eventos concurrentes entre tópicos (desorden)
        await asyncio.sleep(0.8)
        p_q_retry = await db.execute(
            select(Part).where(func.upper(func.trim(Part.sku)) == clean_sku)
        )
        matching_parts = p_q_retry.scalars().all()

    # Si no existe O es ambiguo (más de una pieza con el mismo SKU), va a revisión manual
    if len(matching_parts) != 1:
        part = None
    else:
        part = matching_parts[0]

    if not part:
        # Pieza no identificada: Guardar en unmatched_receipts
        ur = UnmatchedReceipt(
            purchase_line_id=line_id,
            part_number=part_number,
            description=description,
            quantity=quantity,
            work_order_code=work_order_code,
            status="pending",
        )
        db.add(ur)
        await db.flush()

        await kafka_producer.publish(
            "stock.unmatched_receipt",
            data={
                "purchase_line_id": line_id,
                "part_number": part_number,
                "description": description,
                "quantity": quantity,
            },
            key=f"purchase_line:{line_id}",
        )
        return

    # Pieza identificada: Entrada en recepción (U-100 = 100)
    receiving_loc = 100
    now = datetime.now(timezone.utc)
    unit_cost_str = f"{float(unit_price):.2f}" if unit_price is not None else "0.00"

    mov = InventoryMovement(
        movement_type="receipt",
        part_id=part.part_id,
        location_id=receiving_loc,
        delta=quantity,
        reference_id=f"Purchase Line {line_id}",
    )
    db.add(mov)
    await db.flush()

    await kafka_producer.publish(
        "stock.received",
        data={
            "part_id": part.part_id,
            "location_id": receiving_loc,
            "quantity": quantity,
            "unit_cost": unit_cost_str,
            "currency": currency,
            "purchase_line_id": line_id,
        },
        key=f"part:{part.part_id}",
    )

    # Regla FIFO de surtido de faltantes abiertos para esta pieza
    if work_order_code:
        wo_p_q = await db.execute(select(WorkOrder).where(WorkOrder.code == work_order_code))
        target_wo = wo_p_q.scalar_one_or_none()
        if target_wo:
            sh_q_target = await db.execute(
                select(Shortage)
                .where(
                    Shortage.part_id == part.part_id,
                    Shortage.status == "open",
                    Shortage.work_order_id == target_wo.work_order_id,
                )
                .order_by(Shortage.created_at.asc())
            )
            target_shortages = list(sh_q_target.scalars().all())

            sh_q_other = await db.execute(
                select(Shortage)
                .where(
                    Shortage.part_id == part.part_id,
                    Shortage.status == "open",
                    Shortage.work_order_id != target_wo.work_order_id,
                )
                .order_by(Shortage.created_at.asc())
            )
            open_shortages = target_shortages + list(sh_q_other.scalars().all())
        else:
            sh_q = await db.execute(
                select(Shortage)
                .where(Shortage.part_id == part.part_id, Shortage.status == "open")
                .order_by(Shortage.created_at.asc())
            )
            open_shortages = list(sh_q.scalars().all())
    else:
        sh_q = await db.execute(
            select(Shortage)
            .where(Shortage.part_id == part.part_id, Shortage.status == "open")
            .order_by(Shortage.created_at.asc())
        )
        open_shortages = list(sh_q.scalars().all())

    rem_qty = quantity
    for sh in open_shortages:
        if rem_qty <= 0:
            break

        needed = sh.missing_quantity or 1
        fulfill = min(rem_qty, needed)
        rem_qty -= fulfill

        if fulfill >= needed:
            sh.status = "resolved"
        else:
            sh.missing_quantity -= fulfill

        # Convertir el faltante en una reserva activa para esa orden
        res = Reservation(
            work_order_id=sh.work_order_id,
            bom_line_id=sh.bom_line_id,
            part_id=part.part_id,
            quantity=fulfill,
            inspection_item_id=sh.inspection_item_id,
            status="active",
        )
        db.add(res)
        await db.flush()

        wo_q = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == sh.work_order_id))
        wo = wo_q.scalar_one_or_none()
        wo_code = wo.code if wo else f"WO-{sh.work_order_id}"

        await kafka_producer.publish(
            "stock.shortage_resolved",
            data={
                "work_order_id": sh.work_order_id,
                "part_id": part.part_id,
                "quantity": fulfill,
            },
            key=wo_code,
        )
        await kafka_producer.publish(
            "stock.reserved",
            data={
                "reservation_id": res.reservation_id,
                "work_order_id": sh.work_order_id,
                "part_id": part.part_id,
                "quantity": fulfill,
                "inspection_item_id": sh.inspection_item_id,
            },
            key=wo_code,
        )
