import logging
import os
from datetime import datetime
import requests

from workers.celery_app import celery_app
from models.database import SessionLocal
from models.domain import BudgetLine, MasterConcept, Supplier, QuoteRequest

logger = logging.getLogger(__name__)

# Configuración de Evolution API
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")  # ej. http://localhost:8080
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME", "brics_instance")


@celery_app.task(name="workers.tasks.quote_line")
def quote_line_task(budget_line_id: int):
    """Encola solicitudes de cotización para proveedores activos según la familia de la línea."""
    logger.info("Iniciando cotización para BudgetLine ID: %d", budget_line_id)
    db = SessionLocal()
    try:
        bl = db.get(BudgetLine, budget_line_id)
        if not bl:
            logger.error("BudgetLine %d no encontrada", budget_line_id)
            return

        if bl.match_status not in ("auto", "resolved"):
            logger.warning(
                "BudgetLine %d está en estado '%s', no se puede cotizar automáticamente",
                budget_line_id,
                bl.match_status,
            )
            return

        if not bl.matched_concept_id:
            logger.error("BudgetLine %d no tiene un concepto asociado", budget_line_id)
            return

        concept = db.get(MasterConcept, bl.matched_concept_id)
        if not concept:
            logger.error("MasterConcept %d no encontrado", bl.matched_concept_id)
            return

        # Buscar proveedores que manejen la familia
        suppliers = (
            db.query(Supplier)
            .filter(
                Supplier.active == 1,
                Supplier.families.any(concept.family),
            )
            .all()
        )

        if not suppliers:
            logger.warning("No se encontraron proveedores activos para la familia '%s'", concept.family)
            return

        logger.info(
            "Se encontraron %d proveedores para la familia '%s'",
            len(suppliers),
            concept.family,
        )

        for supplier in suppliers:
            # Crear QuoteRequest
            qr = QuoteRequest(
                budget_line_id=bl.id,
                supplier_id=supplier.id,
                status="queued",
            )
            db.add(qr)
            db.flush()  # Para obtener el qr.id

            # Armar mensaje
            msg = (
                f"Hola {supplier.name}, necesito cotización urgente: "
                f"{concept.technical_concept}, cantidad: {bl.quantity or 1} {bl.unit or concept.unit}. "
                f"¿Cuál sería tu precio unitario neto? "
                f"Responder con el precio. Folio: Brics #{qr.id}"
            )

            success = False
            # Intentar enviar vía Evolution API si está configurada
            if EVOLUTION_API_URL and EVOLUTION_API_KEY:
                url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{EVOLUTION_INSTANCE}"
                headers = {
                    "Content-Type": "application/json",
                    "apikey": EVOLUTION_API_KEY,
                }
                payload = {
                    "number": supplier.whatsapp_number,
                    "options": {
                        "delay": 1200,
                        "presence": "composing",
                    },
                    "textMessage": {"text": msg},
                }
                try:
                    logger.info("Enviando WhatsApp a %s vía Evolution API", supplier.whatsapp_number)
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    if response.status_code in (200, 201):
                        success = True
                    else:
                        logger.error(
                            "Error de Evolution API (HTTP %d): %s",
                            response.status_code,
                            response.text,
                        )
                except Exception as e:
                    logger.exception("Excepción al conectar con Evolution API")
            else:
                # Mock del envío en desarrollo local (ROI / Cero complacencia)
                logger.info(
                    "[MOCK WHATSAPP] De: Brics Core -> Para: %s (%s). Mensaje: '%s'",
                    supplier.name,
                    supplier.whatsapp_number,
                    msg,
                )
                success = True

            # Actualizar QuoteRequest
            if success:
                qr.sent_at = datetime.utcnow()
                qr.status = "sent"
                logger.info("QuoteRequest %d marcado como enviado", qr.id)
            else:
                qr.status = "failed"

        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Error en quote_line_task")
        raise
    finally:
        db.close()
