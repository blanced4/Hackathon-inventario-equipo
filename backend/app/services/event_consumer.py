"""
Consumidor oficial de eventos Kafka/Redpanda para el Servicio de Inventario.
Implementa:
  - Regla 22: Drenado completo de shop.catalog antes de procesar transacciones.
  - Consumo continuo de shop.work_orders, shop.inspections, shop.purchasing.
  - Deduplicación idempotente y commit manual de offsets.
  - Ejecutable como módulo independiente o como background task en FastAPI.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services import event_processor, kafka_producer

logger = logging.getLogger(__name__)

_consumer: Optional[AIOKafkaConsumer] = None
_consumer_task: Optional[asyncio.Task] = None
_is_running = False


async def drain_catalog() -> int:
    """
    Regla 22: Drena completamente el catálogo (shop.catalog) antes de transaccionales.
    Devuelve la cantidad de eventos de catálogo procesados.
    """
    logger.info("── Regla 22: Iniciando drenado prioritario de %s ──", settings.KAFKA_TOPIC_CATALOG)
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_CATALOG,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        session_timeout_ms=60000,
        max_poll_interval_ms=300000,
    )

    count = 0
    try:
        await consumer.start()
        while True:
            # Poll con timeout de 3 segundos para detectar que el tópico se vació
            records = await consumer.getmany(timeout_ms=3000, max_records=100)
            if not records:
                logger.info(f"Catálogo drenado al 100%. Total eventos de catálogo: {count}")
                break

            for tp, messages in records.items():
                for msg in messages:
                    try:
                        raw = json.loads(msg.value.decode("utf-8"))
                        async with AsyncSessionLocal() as db:
                            await event_processor.process_event(raw, msg.topic, db)
                        count += 1
                    except Exception as err:
                        logger.error("Error en evento de catálogo offset %d: %s", msg.offset, err)
                await consumer.commit()

    except Exception as exc:
        logger.error("Error durante el drenado del catálogo: %s", exc)
    finally:
        await consumer.stop()

    return count


async def consume_loop() -> None:
    """
    Loop continuo de consumo para los 4 tópicos del taller.
    """
    global _consumer, _is_running
    _is_running = True

    topics = [
        settings.KAFKA_TOPIC_CATALOG,
        settings.KAFKA_TOPIC_WORK_ORDERS,
        settings.KAFKA_TOPIC_INSPECTIONS,
        settings.KAFKA_TOPIC_PURCHASING,
    ]

    _consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        session_timeout_ms=60000,
        max_poll_interval_ms=300000,
    )

    processed_count = 0
    try:
        await _consumer.start()
        logger.info("Consumidor principal iniciado. Escuchando: %s", topics)

        def _topic_priority(tp_obj):
            t = tp_obj.topic
            if t == settings.KAFKA_TOPIC_CATALOG:
                return 0
            if t == settings.KAFKA_TOPIC_WORK_ORDERS:
                return 1
            if t == settings.KAFKA_TOPIC_INSPECTIONS:
                return 2
            return 3

        while _is_running:
            records = await _consumer.getmany(timeout_ms=1000, max_records=50)
            sorted_partitions = sorted(records.items(), key=lambda item: _topic_priority(item[0]))
            for tp, messages in sorted_partitions:
                for msg in messages:
                    try:
                        raw = json.loads(msg.value.decode("utf-8"))
                        async with AsyncSessionLocal() as db:
                            await event_processor.process_event(raw, msg.topic, db)
                        processed_count += 1
                        if processed_count % 50 == 0:
                            logger.info("Progreso de consumo: %d eventos procesados", processed_count)
                    except Exception as err:
                        logger.error("Error en tópico %s offset %d: %s", msg.topic, msg.offset, err)
                await _consumer.commit()

    except asyncio.CancelledError:
        logger.info("Consumidor detenido por cancelación.")
    except Exception as exc:
        logger.error("Error crítico en loop de consumo: %s", exc)
    finally:
        if _consumer:
            await _consumer.stop()
            _consumer = None
        _is_running = False


async def start_consumer() -> None:
    """Inicia el productor y el consumidor en background para FastAPI."""
    global _consumer_task
    try:
        await kafka_producer.start_producer()
        # 1. Drenar catálogo primero
        await drain_catalog()
        # 2. Iniciar loop continuo en tarea de fondo
        _consumer_task = asyncio.create_task(consume_loop(), name="event-consumer-task")
        logger.info("Background consume_loop() programado exitosamente.")
    except Exception as exc:
        logger.error(f"Error al iniciar background consumer: {exc}", exc_info=True)


async def stop_consumer() -> None:
    """Detiene el consumidor de forma limpia."""
    global _consumer_task, _is_running
    _is_running = False
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    await kafka_producer.stop_producer()
    logger.info("Consumidor y productor detenidos.")


# ── Entrada CLI independiente ──────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    )
    logger.info("Iniciando consumo de eventos del taller vía CLI...")

    async def main():
        await kafka_producer.start_producer()
        catalog_count = await drain_catalog()
        logger.info("Fase 1 completada (%d partes/ubicaciones cargadas). Iniciando Fase 2...", catalog_count)
        # Procesar transacciones
        await consume_loop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Consumo detenido por el usuario.")
