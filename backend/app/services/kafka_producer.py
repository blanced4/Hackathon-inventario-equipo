"""
Productor Kafka para publicar eventos en inventory.events.
Cumple estrictamente con el contrato y esquemas oficiales.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: Optional[AIOKafkaProducer] = None


async def start_producer() -> None:
    """Inicia el producer Kafka."""
    global _producer
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await _producer.start()
        logger.info("Kafka producer iniciado → %s", settings.KAFKA_BOOTSTRAP_SERVERS)
    except Exception as exc:
        logger.warning("No se pudo iniciar el producer Kafka: %s", exc)
        _producer = None


async def stop_producer() -> None:
    """Cierra el producer Kafka."""
    global _producer
    if _producer:
        try:
            await _producer.stop()
        except Exception:
            pass
        _producer = None
        logger.info("Kafka producer detenido.")


def _envelope(event_type: str, data: dict[str, Any], key: str) -> dict[str, Any]:
    """Construye el sobre estándar con timestamp en formato ISO 8601 terminado en Z."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "inventory",
        "key": key,
        "data": data,
    }


async def publish(event_type: str, data: dict[str, Any], key: str) -> None:
    """
    Publica un evento en inventory.events con su llave oficial.
    """
    global _producer
    if _producer is None:
        try:
            await start_producer()
        except Exception:
            pass

    if _producer is None:
        logger.warning("Producer no disponible; evento descartado: %s", event_type)
        return

    message = _envelope(event_type, data, key)
    try:
        await _producer.send_and_wait(
            settings.KAFKA_TOPIC_INVENTORY_EVENTS,
            value=message,
            key=key,
        )
        logger.info("Evento publicado a %s: %s (key=%s)", settings.KAFKA_TOPIC_INVENTORY_EVENTS, event_type, key)
    except Exception as exc:
        logger.error("Error publicando evento %s: %s", event_type, exc)
