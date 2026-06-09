"""Audit log helper — insert events for compliance tracking. Fire-and-forget."""
import json
import logging
from typing import Optional, Dict

from sqlalchemy import text

from core.engines import get_engine_knowledge

logger = logging.getLogger(__name__)


def log_event(
    action: str,
    actor_type: str = "system",
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> None:
    """Insert audit_log row. Never raises — best-effort logging."""
    try:
        engine = get_engine_knowledge()
        with engine.begin() as conn:
            # Stash user_agent into detail since schema doesn't have a column for it
            detail = dict(metadata or {})
            if user_agent:
                detail["user_agent"] = user_agent
            conn.execute(
                text("""
                    INSERT INTO audit_log(
                        actor_type, actor_id, action,
                        target_type, target_id, ip_addr, detail
                    ) VALUES (
                        :at, :ai, :a, :tt, :ti, :ip, CAST(:md AS JSONB)
                    )
                """),
                {
                    "at": actor_type,
                    "ai": actor_id,
                    "a": action,
                    "tt": target_type,
                    "ti": target_id,
                    "ip": ip,
                    "md": json.dumps(detail),
                },
            )
    except Exception as e:
        logger.warning(f"audit_log insert failed (action={action}): {e}")
