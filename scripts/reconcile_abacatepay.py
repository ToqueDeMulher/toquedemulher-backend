"""Reconcile expired, abandoned and disputed AbacatePay orders without creating charges."""

import argparse
import logging
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import Database
from app.core.settings import settings
from app.core.time import utc_now
from app.models.payment import Payment, PaymentStatus
from app.services import abacatepay

logger = logging.getLogger(__name__)


def run(limit: int) -> int:
    checked_at = func.coalesce(Payment.provider_checked_at, Payment.created_at)
    with Session(Database.engine) as session:
        order_ids = session.exec(
            select(Payment.order_id)
            .where(
                Payment.provider == abacatepay.PROVIDER,
                Payment.status.in_(abacatepay.ACTIVE_STATUSES),
                Payment.provider_dev_mode == settings.ABACATEPAY_DEV_MODE,
                checked_at < utc_now() - timedelta(minutes=1),
            )
            .order_by(checked_at, Payment.id)
            .limit(limit)
        ).all()

    failures = 0
    for order_id in order_ids:
        with Session(Database.engine) as session:
            payment = abacatepay.payment_for_update(session, order_id)
            if not payment or payment.status not in abacatepay.ACTIVE_STATUSES:
                continue
            try:
                remote = abacatepay.reconcile(session, payment)
                if remote is None and payment.status == PaymentStatus.PENDING.value:
                    failures += 1
                    logger.warning(
                        "Cobrança sem confirmação de emissão: pedido=%s", order_id
                    )
                session.commit()
            except HTTPException as exc:
                session.commit()
                failures += 1
                logger.warning(
                    "Falha de conciliação: pedido=%s status=%s",
                    order_id,
                    exc.status_code,
                )
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, choices=range(1, 501), metavar="1..500", default=100
    )
    args = parser.parse_args()
    raise SystemExit(1 if run(args.limit) else 0)
