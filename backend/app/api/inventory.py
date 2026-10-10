"""
Rutas oficiales del API REST del Servicio de Inventario.
Cumplen al 100% con contract/openapi.yaml y la base de datos Supabase.
"""

from datetime import datetime, timezone
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import kafka_producer
from app.models.models import (
    InventoryMovement,
    Location,
    Part,
    Reservation,
    Shortage,
    UnmatchedReceipt,
    WorkOrder,
    BomLine,
)
from app.schemas.inventory import (
    AdjustmentItem,
    AvailabilityResponse,
    CountRequest,
    CountResponse,
    IssueRequest,
    LedgerEntry,
    LedgerResponse,
    LocationAvailability,
    MaterialLine,
    MovementResponse,
    PartLookupResponse,
    ReorderSuggestionItem,
    ReorderSuggestionsResponse,
    ResolveReceiptRequest,
    ShortageItem,
    ShortagesListResponse,
    TransferRequest,
    UnmatchedReceiptItem,
    UnmatchedReceiptsResponse,
    WorkOrderMaterialsResponse,
)

router = APIRouter(tags=["inventario"])


# ── 1. GET /parts/{part_id}/availability ─────────────────────────────────────
@router.get(
    "/parts/{part_id}/availability",
    response_model=AvailabilityResponse,
    summary="Saldo de pieza total y por estante",
)
async def get_part_availability(
    part_id: int,
    db: AsyncSession = Depends(get_db),
):
    part_q = await db.execute(select(Part).where(Part.part_id == part_id))
    part = part_q.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail=f"Pieza {part_id} no encontrada en catálogo")

    # On hand total = suma de deltas en inventory_movements
    stock_q = await db.execute(
        select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
            InventoryMovement.part_id == part_id
        )
    )
    total_on_hand = int(stock_q.scalar() or 0)

    # Reservas activas totales
    res_q = await db.execute(
        select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
            Reservation.part_id == part_id,
            Reservation.status == "active",
        )
    )
    total_reserved = int(res_q.scalar() or 0)
    # Regla del contrato: available = on_hand - reserved, nunca por debajo de cero
    total_available = max(0, total_on_hand - total_reserved)

    # On hand agrupado por ubicación
    loc_stock_q = await db.execute(
        select(
            InventoryMovement.location_id,
            func.coalesce(func.sum(InventoryMovement.delta), 0).label("on_hand"),
        )
        .where(InventoryMovement.part_id == part_id)
        .group_by(InventoryMovement.location_id)
    )
    loc_rows = loc_stock_q.all()

    locations_list = []
    for r in loc_rows:
        loc_id = r.location_id
        loc_on_hand = int(r.on_hand)
        if loc_on_hand <= 0:
            continue

        loc_meta_q = await db.execute(select(Location).where(Location.location_id == loc_id))
        loc_meta = loc_meta_q.scalar_one_or_none()
        code = loc_meta.code if loc_meta else f"U-{loc_id}"

        # Disponibilidad local
        loc_available = max(0, loc_on_hand - total_reserved)

        locations_list.append(
            LocationAvailability(
                location_id=loc_id,
                code=code,
                on_hand=loc_on_hand,
                reserved=total_reserved,
                available=loc_available,
            )
        )

    return AvailabilityResponse(
        part_id=part_id,
        name=part.name,
        sku=part.sku,
        on_hand=total_on_hand,
        reserved=total_reserved,
        available=total_available,
        locations=locations_list,
    )


# ── 1b. GET /parts/lookup?code=... (Resolver etiqueta escaneada) ─────────────
@router.get(
    "/parts/lookup",
    response_model=PartLookupResponse,
    summary="Resolver una pieza desde un código escaneado (ID, SKU o nombre)",
    tags=["scanner"],
)
async def lookup_part_by_code(
    code: str = Query(..., description="Texto del código de barras/QR escaneado"),
    db: AsyncSession = Depends(get_db),
):
    """Busca una pieza a partir del texto escaneado del kit de etiquetas.

    Soporta tres formatos:
      - ``P-24`` o ``24``      → por part_id
      - ``INSERTO-001``        → por SKU exacto (case-insensitive)
      - ``TORNILLO 6X12``      → por nombre (coincidencia exacta o parcial)
    """
    raw = (code or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Código vacío")

    part = None
    matched_by = ""

    # 1) Formato P-<id> o solo dígitos → part_id
    import re
    pid_match = re.fullmatch(r"[Pp]-?(\d+)", raw) or re.fullmatch(r"(\d+)", raw)
    if pid_match:
        pid = int(pid_match.group(1))
        q = await db.execute(select(Part).where(Part.part_id == pid))
        part = q.scalar_one_or_none()
        if part:
            matched_by = "id"

    # 2) Por SKU exacto (case-insensitive)
    if part is None:
        q = await db.execute(select(Part).where(func.lower(Part.sku) == raw.lower()))
        part = q.scalar_one_or_none()
        if part:
            matched_by = "sku"

    # 3) Por nombre exacto (case-insensitive)
    if part is None:
        q = await db.execute(select(Part).where(func.lower(Part.name) == raw.lower()))
        part = q.scalar_one_or_none()
        if part:
            matched_by = "name"

    # 4) Por nombre parcial (contains)
    if part is None:
        q = await db.execute(
            select(Part).where(Part.name.ilike(f"%{raw}%")).limit(1)
        )
        part = q.scalar_one_or_none()
        if part:
            matched_by = "name"

    if part is None:
        raise HTTPException(status_code=404, detail=f"No se encontró ninguna pieza para el código '{raw}'")

    # Stock total on-hand
    stock_q = await db.execute(
        select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
            InventoryMovement.part_id == part.part_id
        )
    )
    total_on_hand = int(stock_q.scalar() or 0)

    return PartLookupResponse(
        part_id=part.part_id,
        sku=part.sku,
        name=part.name,
        on_hand=total_on_hand,
        matched_by=matched_by,
    )


# ── 2. GET /parts/{part_id}/ledger ───────────────────────────────────────────
@router.get(
    "/parts/{part_id}/ledger",
    response_model=LedgerResponse,
    summary="Kardex de la pieza ordenado por fecha con saldo corrido",
)
async def get_part_ledger(
    part_id: int,
    db: AsyncSession = Depends(get_db),
):
    part_q = await db.execute(select(Part).where(Part.part_id == part_id))
    if not part_q.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Pieza no encontrada")

    movs_q = await db.execute(
        select(InventoryMovement)
        .where(InventoryMovement.part_id == part_id)
        .order_by(InventoryMovement.created_at.asc(), InventoryMovement.movement_id.asc())
    )
    movs = movs_q.scalars().all()

    running_balance = 0
    entries = []
    for m in movs:
        running_balance += m.delta
        entries.append(
            LedgerEntry(
                movement_id=m.movement_id,
                type=m.movement_type,
                part_id=m.part_id,
                location_id=m.location_id,
                quantity=m.delta,
                occurred_at=m.created_at or datetime.now(timezone.utc),
                reference=m.reference_id,
                balance=running_balance,
            )
        )

    entries.reverse()
    return LedgerResponse(part_id=part_id, entries=entries)


# ── 3. GET /work-orders/{code}/materials ─────────────────────────────────────
@router.get(
    "/work-orders/{code}/materials",
    response_model=WorkOrderMaterialsResponse,
    summary="Materiales de la orden con requeridos, reservados y faltantes",
)
async def get_work_order_materials(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    wo_q = await db.execute(select(WorkOrder).where(WorkOrder.code == code))
    wo = wo_q.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    bom_q = await db.execute(
        select(BomLine).where(BomLine.model_id == wo.model_id)
    )
    bom_lines = bom_q.scalars().all()

    lines = []
    for idx, bl in enumerate(bom_lines, start=1):
        # Reservas activas
        res_conditions = [Reservation.work_order_id == wo.work_order_id, Reservation.status == "active"]
        if bl.part_id:
            res_conditions.append(
                or_(
                    Reservation.bom_line_id == bl.bom_line_id,
                    and_(Reservation.bom_line_id.is_(None), Reservation.part_id == bl.part_id),
                )
            )
        else:
            res_conditions.append(Reservation.bom_line_id == bl.bom_line_id)

        res_q = await db.execute(
            select(func.coalesce(func.sum(Reservation.quantity), 0)).where(*res_conditions)
        )
        reserved_qty = int(res_q.scalar() or 0)

        # Faltantes abiertos
        short_conditions = [Shortage.work_order_id == wo.work_order_id, Shortage.status == "open"]
        if bl.part_id:
            short_conditions.append(
                or_(
                    Shortage.bom_line_id == bl.bom_line_id,
                    and_(Shortage.bom_line_id.is_(None), Shortage.part_id == bl.part_id),
                )
            )
        else:
            short_conditions.append(Shortage.bom_line_id == bl.bom_line_id)

        short_q = await db.execute(
            select(func.coalesce(func.sum(Shortage.missing_quantity), 0)).where(*short_conditions)
        )
        missing_qty = int(short_q.scalar() or 0)

        # Salidas registradas para esta orden y pieza
        issued_qty = 0
        if bl.part_id:
            iss_q = await db.execute(
                select(func.coalesce(func.sum(-InventoryMovement.delta), 0)).where(
                    InventoryMovement.movement_type == "issue",
                    InventoryMovement.reference_id == wo.code,
                    InventoryMovement.part_id == bl.part_id,
                )
            )
            issued_qty = int(iss_q.scalar() or 0)

        # Requerido: suma de reservado + faltante + entregado si hubo inspección; si no, del catálogo
        if reserved_qty + missing_qty + issued_qty > 0:
            required_qty = reserved_qty + missing_qty + issued_qty
        else:
            required_qty = bl.qty_per_unit

        lines.append(
            MaterialLine(
                inspection_item_id=bl.sort_order if bl.sort_order else idx,
                bom_line_id=bl.bom_line_id,
                part_id=bl.part_id,
                name=bl.name,
                required=required_qty,
                reserved=reserved_qty,
                issued=issued_qty,
                missing=missing_qty if missing_qty > 0 else 0,
            )
        )

    return WorkOrderMaterialsResponse(
        work_order_id=wo.work_order_id,
        code=wo.code,
        lines=lines,
    )


# ── 4. GET /shortages ────────────────────────────────────────────────────────
@router.get(
    "/shortages",
    response_model=ShortagesListResponse,
    summary="Faltantes abiertos",
)
async def get_open_shortages(
    work_order_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Shortage, WorkOrder.code.label("wo_code"))
        .outerjoin(WorkOrder, Shortage.work_order_id == WorkOrder.work_order_id)
        .where(
            Shortage.status == "open",
            or_(WorkOrder.is_deleted == False, WorkOrder.is_deleted.is_(None)),
        )
    )
    if work_order_code:
        query = query.where(WorkOrder.code == work_order_code)

    query = query.order_by(Shortage.created_at.asc())
    short_q = await db.execute(query)
    rows = short_q.all()

    items = []
    for s, wo_code in rows:
        items.append(
            ShortageItem(
                work_order_id=s.work_order_id,
                work_order_code=wo_code or f"WO-{s.work_order_id}",
                part_id=s.part_id,
                name=s.name,
                missing_quantity=s.missing_quantity,
                inspection_item_id=s.inspection_item_id or 1,
                opened_at=s.created_at,
            )
        )

    return ShortagesListResponse(items=items)


# ── 5. GET /reorder-suggestions ──────────────────────────────────────────────
@router.get(
    "/reorder-suggestions",
    response_model=ReorderSuggestionsResponse,
    summary="Sugerencias de compra para reabasto",
)
@router.get(
    "/purchasing/reorder-suggestions",
    response_model=ReorderSuggestionsResponse,
    include_in_schema=False,
)
async def get_reorder_suggestions(db: AsyncSession = Depends(get_db)):
    short_q = await db.execute(
        select(
            Shortage.part_id,
            Part.sku,
            Part.name,
            func.sum(Shortage.missing_quantity).label("suggested"),
        )
        .join(Part, Shortage.part_id == Part.part_id)
        .where(Shortage.status == "open", Shortage.part_id.isnot(None))
        .group_by(Shortage.part_id, Part.sku, Part.name)
    )
    rows = short_q.all()

    items = []
    for r in rows:
        wo_ids_q = await db.execute(
            select(Shortage.work_order_id)
            .where(Shortage.part_id == r.part_id, Shortage.status == "open")
            .distinct()
        )
        wo_ids = [w[0] for w in wo_ids_q.fetchall()]

        items.append(
            ReorderSuggestionItem(
                part_id=r.part_id,
                sku=r.sku,
                name=r.name,
                suggested_quantity=int(r.suggested or 0),
                work_order_ids=wo_ids,
            )
        )

    return ReorderSuggestionsResponse(items=items)


# ── 6. GET /unmatched-receipts ───────────────────────────────────────────────
@router.get(
    "/unmatched-receipts",
    response_model=UnmatchedReceiptsResponse,
    summary="Compras que llegaron a recepción y no se identificaron",
)
@router.get(
    "/purchasing/unmatched-receipts",
    response_model=UnmatchedReceiptsResponse,
    include_in_schema=False,
)
async def get_unmatched_receipts(db: AsyncSession = Depends(get_db)):
    unmatched_q = await db.execute(
        select(UnmatchedReceipt).where(UnmatchedReceipt.status == "pending")
    )
    rows = unmatched_q.scalars().all()

    items = []
    for r in rows:
        items.append(
            UnmatchedReceiptItem(
                id=r.id,
                purchase_line_id=r.purchase_line_id,
                part_number=r.part_number,
                description=r.description or "",
                quantity=r.quantity,
                unit_price="0.00",
                currency="MXN",
                received_at=r.received_at,
                work_order_code=r.work_order_code,
            )
        )

    return UnmatchedReceiptsResponse(items=items)


# ── 7. POST /issues (Salida por escaneo sin permitir negativos) ──────────────
@router.post(
    "/issues",
    status_code=status.HTTP_201_CREATED,
    response_model=MovementResponse,
    summary="Salida de material para una orden",
)
@router.post(
    "/operations/issue",
    status_code=status.HTTP_201_CREATED,
    response_model=MovementResponse,
    include_in_schema=False,
)
async def issue_part(req: IssueRequest, db: AsyncSession = Depends(get_db)):
    # Validar disponibilidad real en esa ubicación
    stk_q = await db.execute(
        select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
            InventoryMovement.part_id == req.part_id,
            InventoryMovement.location_id == req.location_id,
        )
    )
    location_on_hand = int(stk_q.scalar() or 0)

    if location_on_hand < req.quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Saldo insuficiente en ubicación (disponible: {location_on_hand}, solicitado: {req.quantity})",
        )

    movement = InventoryMovement(
        movement_type="issue",
        part_id=req.part_id,
        location_id=req.location_id,
        delta=-req.quantity,
        reference_id=req.work_order_code,
    )
    db.add(movement)

    wo_q = await db.execute(select(WorkOrder).where(WorkOrder.code == req.work_order_code))
    wo = wo_q.scalar_one_or_none()
    if wo:
        res_q = await db.execute(
            select(Reservation).where(
                Reservation.work_order_id == wo.work_order_id,
                Reservation.part_id == req.part_id,
                Reservation.status == "active",
            )
        )
        res_q = await db.execute(
            select(Reservation).where(
                Reservation.work_order_id == wo.work_order_id,
                Reservation.part_id == req.part_id,
                Reservation.status == "active",
            ).order_by(Reservation.created_at.asc())
        )
        rem_fulfill = req.quantity
        for res_obj in res_q.scalars().all():
            if rem_fulfill <= 0:
                break
            if res_obj.quantity <= rem_fulfill:
                rem_fulfill -= res_obj.quantity
                res_obj.quantity = 0
                res_obj.status = "fulfilled"
            else:
                res_obj.quantity -= rem_fulfill
                rem_fulfill = 0

    await db.commit()
    await db.refresh(movement)

    await kafka_producer.publish(
        "stock.issued",
        data={
            "work_order_id": wo.work_order_id if wo else 0,
            "part_id": req.part_id,
            "location_id": req.location_id,
            "quantity": req.quantity,
            "issued_by": req.issued_by,
        },
        key=req.work_order_code,
    )

    return MovementResponse(
        movement_id=movement.movement_id,
        type=movement.movement_type,
        part_id=movement.part_id,
        location_id=movement.location_id,
        quantity=movement.delta,
        occurred_at=movement.created_at,
        reference=movement.reference_id,
    )


# ── 8. POST /transfers (Transferencia entre ubicaciones) ──────────────────────
@router.post(
    "/transfers",
    status_code=status.HTTP_201_CREATED,
    response_model=MovementResponse,
    summary="Transferencia entre ubicaciones",
)
@router.post(
    "/operations/transfer",
    status_code=status.HTTP_201_CREATED,
    response_model=MovementResponse,
    include_in_schema=False,
)
async def transfer_part(req: TransferRequest, db: AsyncSession = Depends(get_db)):
    stock_q = await db.execute(
        select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
            InventoryMovement.part_id == req.part_id,
            InventoryMovement.location_id == req.from_location_id,
        )
    )
    origin_stock = int(stock_q.scalar() or 0)

    if origin_stock < req.quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Saldo insuficiente en origen (disponible: {origin_stock}, solicitado: {req.quantity})",
        )

    mov_out = InventoryMovement(
        movement_type="transfer_out",
        part_id=req.part_id,
        location_id=req.from_location_id,
        delta=-req.quantity,
        reference_id=f"Transfer to {req.to_location_id}",
    )
    mov_in = InventoryMovement(
        movement_type="transfer_in",
        part_id=req.part_id,
        location_id=req.to_location_id,
        delta=req.quantity,
        reference_id=f"Transfer from {req.from_location_id}",
    )
    db.add(mov_out)
    db.add(mov_in)
    await db.commit()
    await db.refresh(mov_in)

    await kafka_producer.publish(
        "stock.transferred",
        data={
            "part_id": req.part_id,
            "from_location_id": req.from_location_id,
            "to_location_id": req.to_location_id,
            "quantity": req.quantity,
        },
        key=f"part:{req.part_id}",
    )

    return MovementResponse(
        movement_id=mov_in.movement_id,
        type=mov_in.movement_type,
        part_id=mov_in.part_id,
        location_id=mov_in.location_id,
        quantity=mov_in.delta,
        occurred_at=mov_in.created_at,
        reference=mov_in.reference_id,
    )


# ── 9. POST /counts (Conteo físico con ajustes) ──────────────────────────────
@router.post(
    "/counts",
    status_code=status.HTTP_201_CREATED,
    response_model=CountResponse,
    summary="Conteo cíclico con ajustes",
)
@router.post(
    "/operations/count",
    status_code=status.HTTP_201_CREATED,
    response_model=CountResponse,
    include_in_schema=False,
)
async def cycle_count(req: CountRequest, db: AsyncSession = Depends(get_db)):
    if not req.reason.strip():
        raise HTTPException(status_code=422, detail="El motivo del ajuste es obligatorio")

    adjustments = []
    for line in req.lines:
        stk_q = await db.execute(
            select(func.coalesce(func.sum(InventoryMovement.delta), 0)).where(
                InventoryMovement.part_id == line.part_id,
                InventoryMovement.location_id == req.location_id,
            )
        )
        current_qty = int(stk_q.scalar() or 0)
        delta = line.counted_quantity - current_qty

        if delta != 0:
            adj_mov = InventoryMovement(
                movement_type="adjustment",
                part_id=line.part_id,
                location_id=req.location_id,
                delta=delta,
                reference_id=req.reason,
            )
            db.add(adj_mov)
            adjustments.append(AdjustmentItem(part_id=line.part_id, delta=delta))

    await db.commit()

    for adj in adjustments:
        await kafka_producer.publish(
            "stock.adjusted",
            data={
                "part_id": adj.part_id,
                "location_id": req.location_id,
                "delta": adj.delta,
                "reason": req.reason,
            },
            key=f"part:{adj.part_id}",
        )

    return CountResponse(adjustments=adjustments)


# ── 10. POST /unmatched-receipts/{id}/resolve ────────────────────────────────
@router.post(
    "/unmatched-receipts/{id}/resolve",
    status_code=status.HTTP_200_OK,
    response_model=MovementResponse,
    summary="Relacionar a mano una recepción con una pieza",
)
async def resolve_unmatched_receipt(
    id: int,
    req: ResolveReceiptRequest,
    db: AsyncSession = Depends(get_db),
):
    receipt_q = await db.execute(
        select(UnmatchedReceipt).where(UnmatchedReceipt.id == id)
    )
    receipt = receipt_q.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    if receipt.status == "resolved":
        raise HTTPException(status_code=409, detail="La recepción ya fue resuelta")

    loc_id = req.location_id or 100
    receipt.status = "resolved"
    receipt.resolved_part_id = req.part_id

    receipt_mov = InventoryMovement(
        movement_type="receipt",
        part_id=req.part_id,
        location_id=loc_id,
        delta=receipt.quantity,
        reference_id=f"Resolved purchase line {receipt.purchase_line_id}",
    )
    db.add(receipt_mov)
    await db.commit()
    await db.refresh(receipt_mov)

    unit_cost_str = "0.00"
    await kafka_producer.publish(
        "stock.received",
        data={
            "part_id": req.part_id,
            "location_id": loc_id,
            "quantity": receipt.quantity,
            "unit_cost": unit_cost_str,
            "currency": "MXN",
            "purchase_line_id": receipt.purchase_line_id,
        },
        key=f"part:{req.part_id}",
    )

    return MovementResponse(
        movement_id=receipt_mov.movement_id,
        type=receipt_mov.movement_type,
        part_id=receipt_mov.part_id,
        location_id=receipt_mov.location_id,
        quantity=receipt_mov.delta,
        occurred_at=receipt_mov.created_at,
        reference=receipt_mov.reference_id,
    )


# ── 11. POST /purchasing/unmatched-receipts/{id}/ai-match ─────────────────────
from pydantic import BaseModel
from app.services.gemini_service import (
    match_unmatched_receipt_with_gemini,
    ask_industrial_copilot,
    AIMatchResult,
    AICopilotResponse,
)


@router.post(
    "/unmatched-receipts/{id}/ai-match",
    response_model=AIMatchResult,
    summary="Analizar recepción con Gemini AI y sugerir pieza del catálogo",
    tags=["ai"],
)
@router.post(
    "/purchasing/unmatched-receipts/{id}/ai-match",
    response_model=AIMatchResult,
    include_in_schema=False,
)
async def ai_match_receipt(id: int, db: AsyncSession = Depends(get_db)):
    """Analiza una recepción no asociada usando Gemini AI y devuelve la pieza sugerida."""
    receipt_q = await db.execute(select(UnmatchedReceipt).where(UnmatchedReceipt.id == id))
    receipt = receipt_q.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")

    parts_q = await db.execute(select(Part))
    parts = [{"part_id": p.part_id, "sku": p.sku, "name": p.name} for p in parts_q.scalars().all()]

    short_q = await db.execute(select(Shortage).where(Shortage.status == "open"))
    shortages = [{"part_id": s.part_id, "name": s.name, "missing": s.missing_quantity} for s in short_q.scalars().all()]

    receipt_dict = {
        "part_number": receipt.part_number,
        "description": receipt.description,
        "quantity": receipt.quantity,
        "work_order_code": receipt.work_order_code,
    }

    return await match_unmatched_receipt_with_gemini(receipt_dict, parts, shortages)


# ── 12. POST /purchasing/unmatched-receipts/{id}/ai-resolve ───────────────────
@router.post(
    "/unmatched-receipts/{id}/ai-resolve",
    response_model=MovementResponse,
    summary="Resolver recepción automáticamente usando sugerencia de Gemini AI",
    tags=["ai"],
)
@router.post(
    "/purchasing/unmatched-receipts/{id}/ai-resolve",
    response_model=MovementResponse,
    include_in_schema=False,
)
async def ai_resolve_receipt(id: int, db: AsyncSession = Depends(get_db)):
    """Ejecuta el emparejamiento con Gemini y asocia la recepción directamente al Kardex."""
    match_result = await ai_match_receipt(id=id, db=db)
    if not match_result.suggested_part_id:
        raise HTTPException(
            status_code=422,
            detail="Gemini AI no pudo encontrar una coincidencia con suficiente certeza en el catálogo",
        )

    req = ResolveReceiptRequest(part_id=match_result.suggested_part_id, location_id=100)
    return await resolve_unmatched_receipt(id=id, req=req, db=db)


class CopilotQueryRequest(BaseModel):
    query: str


# ── 13. POST /ai/copilot ──────────────────────────────────────────────────────
@router.post(
    "/ai/copilot",
    response_model=AICopilotResponse,
    summary="Copiloto industrial en lenguaje natural con Gemini AI",
    tags=["ai"],
)
async def industrial_copilot_endpoint(req: CopilotQueryRequest, db: AsyncSession = Depends(get_db)):
    """Consulta en lenguaje natural al copiloto del almacén."""
    # 1. Total faltantes y top componentes con mayor faltante
    short_items_q = await db.execute(
        select(Shortage.name, func.sum(func.coalesce(Shortage.missing_quantity, 1)).label("qty"))
        .where(Shortage.status == "open")
        .group_by(Shortage.name)
        .order_by(desc("qty"))
        .limit(5)
    )
    top_shortages = [{"name": r[0], "missing": int(r[1] or 1)} for r in short_items_q.all()]

    total_shortages_q = await db.execute(
        select(func.count(Shortage.shortage_id)).where(Shortage.status == "open")
    )
    total_shortages = total_shortages_q.scalar() or 0

    # 2. Órdenes con faltantes críticos
    orders_q = await db.execute(
        select(WorkOrder.code, func.count(Shortage.shortage_id).label("shortages_count"))
        .join(Shortage, Shortage.work_order_id == WorkOrder.work_order_id)
        .where(Shortage.status == "open", or_(WorkOrder.is_deleted == False, WorkOrder.is_deleted.is_(None)))
        .group_by(WorkOrder.code)
        .order_by(desc("shortages_count"))
        .limit(5)
    )
    critical_orders = [{"code": r[0], "count": r[1]} for r in orders_q.all()]

    # 3. Total y muestras de recepciones pendientes en muelle
    unmatched_count_q = await db.execute(
        select(func.count(UnmatchedReceipt.id)).where(UnmatchedReceipt.status == "pending")
    )
    total_unmatched = unmatched_count_q.scalar() or 0

    unmatched_samples_q = await db.execute(
        select(UnmatchedReceipt.part_number, UnmatchedReceipt.description, UnmatchedReceipt.quantity)
        .where(UnmatchedReceipt.status == "pending")
        .limit(5)
    )
    recent_unmatched = [
        {"part_number": r[0], "description": r[1], "quantity": r[2]}
        for r in unmatched_samples_q.all()
    ]

    shop_context = {
        "total_shortages": total_shortages,
        "total_unmatched": total_unmatched,
        "top_shortages": top_shortages,
        "critical_orders": critical_orders,
        "recent_unmatched": recent_unmatched,
    }

    return await ask_industrial_copilot(req.query, shop_context)

