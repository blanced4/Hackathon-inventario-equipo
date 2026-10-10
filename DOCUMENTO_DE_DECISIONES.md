# Documento de Decisiones — Almacén Inteligente para Taller
**Equipo:** KRAFTWERK SPINDLE-OS · HackaTecNM 2026
**Arquitectura:** FastAPI (Python) + PostgreSQL (Supabase) + Redpanda (Kafka)

El servicio consume los cuatro tópicos del taller (`shop.catalog`, `shop.work_orders`,
`shop.inspections`, `shop.purchasing`), mantiene el inventario como un **libro mayor
inmutable de movimientos** y publica sus propios eventos en `inventory.events`. El stock
nunca se edita: `on_hand` se calcula siempre como la suma de los `delta` de los movimientos,
y `available = max(0, on_hand − reserved)` para no violar la regla de no-negativos.

---

## 1. Cómo relacionamos compras con el catálogo

Las compras (`purchase.item_received`) traen un `part_number` en **texto libre**, no un
`part_id`. Para relacionarlas con el catálogo:

- **Normalizamos y comparamos contra el `sku`** del catálogo de forma tolerante:
  convertimos ambos a mayúsculas y recortamos espacios (`UPPER(TRIM(sku)) = UPPER(TRIM(part_number))`),
  tal como lo pide el contrato ("puede variar en espacios o mayúsculas").
- **Si coincide exactamente una pieza**, registramos una entrada (`receipt`) en la ubicación
  de recepción **U-100** y publicamos `stock.received`. Si la compra trae `work_order_code`,
  surtimos primero el faltante de esa orden (prioridad FIFO para esa orden, luego el resto).
- **Si no coincide ninguna, o coincide más de una (ambigüedad)**, la mandamos a revisión manual:
  se guarda en `unmatched_receipts` y publicamos `stock.unmatched_receipt`. Desde la API
  (`POST /unmatched-receipts/{id}/resolve`) o con asistencia de IA se relaciona a mano.
- **Tolerancia al desorden:** como catálogo y compras llegan por tópicos distintos sin orden
  garantizado, si no encontramos la pieza reintentamos tras una breve espera antes de darla
  por no identificada.
- Las compras con `purpose = customer_order` **no entran al inventario**: solo `restock`.

## 2. Cómo manejamos los kits

Seguimos la definición del contrato: las líneas de un modelo con el mismo `group_name` forman
un kit; si `group_name` es `null`, el kit lo forman las líneas con el mismo `name`.

- **Inventariamos los componentes, no el kit como un todo.** Cada `bom_line` se trata como una
  necesidad individual de pieza, porque el stock real, las reservas y las salidas ocurren a
  nivel de pieza (`part_id`), no de agrupación. Guardamos `group_name` en cada línea para poder
  agrupar en las vistas, pero las reservas y faltantes se calculan por componente.
- Una línea con `part_id = null` (pieza sin identificar) **no se puede reservar**: se reporta
  como faltante sin identificar (`stock.shortage_detected` con `part_id: null`).

## 3. Cómo evitamos reservas dobles

Una orden puede recibir varias inspecciones aprobadas (una rápida y luego completas),
normalmente con las mismas piezas. Para no duplicar reservas:

- **Reemplazo por línea de inspección.** Al llegar una nueva `inspection.approved`, antes de
  reservar marcamos como `superseded` las reservas activas y los faltantes abiertos previos de
  esa misma `(work_order, bom_line)` —o `(work_order, part_id)` si no hay `bom_line`—. Así la
  última aprobación es la que manda y no se acumulan reservas repetidas.
- **Control de concurrencia / sin negativos.** La disponibilidad se calcula justo antes de
  reservar y nunca se reserva más de lo disponible: si no alcanza, se reserva lo que hay y el
  resto se vuelve faltante. Dos aprobaciones no pueden apartar la misma última pieza porque
  cada reserva se valida contra el saldo real en el momento de aplicarse.
- **Liberación.** Si una orden se da de baja (`work_order.deleted`) o una inspección se anula
  (`inspection.voided` / `rejected` / `discarded`), liberamos (`cancelled`) sus reservas activas
  y cerramos sus faltantes abiertos.

## 4. Cómo garantizamos idempotencia

- **Deduplicación por `event_id`.** Cada evento procesado se registra en la tabla
  `processed_events`. Antes de procesar cualquier evento verificamos si su `event_id` ya existe;
  si es así, lo ignoramos. Reenviar el mismo evento no cambia el estado.
- **Transacción atómica.** El efecto del evento (movimientos, reservas, faltantes) y el registro
  en `processed_events` se confirman en la **misma transacción**: o se aplica todo, o nada.
- **Reconstruible desde cero.** Como el estado es la suma de movimientos y el consumidor lee
  los tópicos desde el inicio (`earliest`) drenando primero el catálogo, borrar la base y releer
  produce exactamente el mismo saldo.
- **Tolerancia a errores (DLQ).** Un evento que no se puede procesar se reintenta; si tras los
  reintentos sigue fallando, se envía a `inventory.dlq` con el detalle del error y el consumo
  **continúa sin detenerse**.
