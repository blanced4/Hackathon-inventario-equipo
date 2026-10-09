---
inclusion: always
---

# Kiro Steering Directive — Servicio de Inventario Inteligente (Hackathon)

## Contexto del Sistema

Estamos construyendo un servicio de inventario para un taller de reparación de husillos y motores industriales.

El sistema interactúa consumiendo eventos de un broker Kafka (Redpanda) y publicando eventos de inventario en `inventory.events`.

## Reglas Infranqueables de Desarrollo

1. **Contrato Estricto:** La API HTTP y los eventos de salida deben cumplir al 100% las especificaciones en la carpeta `/contract` (OpenAPI Spec y JSON Schemas).

2. **Idempotencia Obligatoria:** Todos los eventos de entrada deben ser deduplicados mediante `event_id` guardado en PostgreSQL.

3. **Libro Mayor Inmutable (Ledger):** El stock nunca se edita directamente en la base de datos. Se calcula como la suma acumulada de los movimientos de la tabla `inventory_movements`.

4. **Resguardo de Concurrencia:** Ninguna reserva o salida puede dejar el saldo disponible (`available`) por debajo de cero.

5. **Stack Tecnológico:**

   - **Backend:** Python 3.11+ con FastAPI y `aiokafka`.

   - **Base de Datos:** PostgreSQL (vía Supabase).

   - **Frontend:** Next.js 14 (App Router), TailwindCSS, shadcn/ui.

   - **AI Module:** Gemini 1.5 Flash API para resolución semántica de `unmatched-receipts`.

## Eventos Clave a Consumir

- `shop.catalog`: `part.upserted`, `location.upserted`, `bom.upserted`

- `shop.work_orders`: `work_order.opened`, `work_order.stage_changed`, `work_order.deleted`

- `shop.inspections`: `inspection.approved`, `inspection.rejected`, `inspection.voided`

- `shop.purchasing`: `purchase.item_received`

## Eventos a Publicar (`inventory.events`)

- `stock.received`, `stock.unmatched_receipt`, `stock.reserved`, `stock.shortage_detected`, `stock.shortage_resolved`, `stock.issued`, `stock.transferred`, `stock.adjusted`, `stock.reorder_suggested`
