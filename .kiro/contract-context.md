---
inclusion: always
---

# Especificaciones de Datos y Payload (Reto Almacén Inteligente)

## 1. Tópicos de Entrada (Broker Kafka / Redpanda)

Todos los eventos vienen con el sobre:

```json
{
  "event_id": "UUID",
  "event_type": "string",
  "event_version": 1,
  "occurred_at": "ISO-8601-UTC",
  "source": "shop-floor",
  "key": "string",
  "data": {}
}
```

### Eventos de Entrada:

- `part.upserted` (tópico: `shop.catalog`): `part_id`, `sku`, `name`, `family`, `group`, `subgroup`, `unit`, `image_url`, `active`.

- `location.upserted` (tópico: `shop.catalog`): `location_id`, `code` (ej: U-014, U-100), `name`, `is_workbench`, `active`.

- `bom.upserted` (tópico: `shop.catalog`): `model_id`, `model_name`, `brand`, `lines[]` (`bom_line_id`, `part_id`, `name`, `group_name`, `unit`, `qty_per_unit`, `sort_order`).

- `work_order.opened` (tópico: `shop.work_orders`): `work_order_id`, `code`, `model_id`, `department`, `received_at`.

- `work_order.stage_changed` (tópico: `shop.work_orders`): `work_order_id`, `from_stage`, `to_stage`.

- `work_order.deleted` (tópico: `shop.work_orders`): `work_order_id`, `code`.

- `inspection.submitted` (tópico: `shop.inspections`): `inspection_id`, `work_order_id`, `kind`, `items[]` (`inspection_item_id`, `bom_line_id`, `part_id`, `name`, `group_name`, `condition` [ok/damaged/missing], `action` [buy/repair/null], `quantity`, `note`).

- `inspection.approved` (tópico: `shop.inspections`): igual a `submitted` + `approved_by`, `approved_at`.

- `inspection.rejected` / `inspection.discarded` / `inspection.voided` (tópico: `shop.inspections`).

- `purchase.item_received` (tópico: `shop.purchasing`): `purchase_request_id`, `request_number`, `line_id`, `part_number`, `description`, `quantity`, `unit_price`, `currency`, `purpose` (`restock` | `customer_order`), `received_at`, `work_order_code`.

## 2. Eventos de Salida (Tópico: `inventory.events`)

Mismo sobre con `source: "inventory"`.

- `stock.received`: `part_id`, `location_id`, `quantity`, `unit_cost`, `currency`, `purchase_line_id`.

- `stock.unmatched_receipt`: `purchase_line_id`, `part_number`, `description`, `quantity`.

- `stock.reserved`: `reservation_id`, `work_order_id`, `part_id`, `quantity`, `inspection_item_id`.

- `stock.shortage_detected`: `work_order_id`, `part_id` (null), `name`, `missing_quantity`, `inspection_item_id`.

- `stock.shortage_resolved`: `work_order_id`, `part_id`, `quantity`.

- `stock.issued`: `work_order_id`, `part_id`, `location_id`, `quantity`, `issued_by`.

- `stock.transferred`: `part_id`, `from_location_id`, `to_location_id`, `quantity`.

- `stock.adjusted`: `part_id`, `location_id`, `delta`, `reason`.

- `stock.reorder_suggested`: `part_id`, `suggested_quantity`, `work_order_ids[]`.

## 3. Rutas de API HTTP a Implementar

| Método | Ruta                                    | Descripción                                      |
|--------|-----------------------------------------|--------------------------------------------------|
| GET    | `/parts/{part_id}/availability`         | Stock disponible por parte y ubicación           |
| GET    | `/parts/{part_id}/ledger`               | Libro mayor de movimientos (inmutable)           |
| GET    | `/work-orders/{code}/materials`         | Materiales requeridos / reservados por OT        |
| GET    | `/shortages`                            | Faltantes activos detectados                     |
| GET    | `/reorder-suggestions`                  | Sugerencias de reorden generadas por el sistema  |
| GET    | `/unmatched-receipts`                   | Recepciones sin coincidencia de parte            |
| POST   | `/unmatched-receipts/{id}/resolve`      | Resolver recepción no coincidente (vía Gemini)   |
| POST   | `/issues`                               | Registrar salida de material a OT                |
| POST   | `/transfers`                            | Transferir stock entre ubicaciones               |
| POST   | `/counts`                               | Registrar conteo físico (ajuste de inventario)   |
