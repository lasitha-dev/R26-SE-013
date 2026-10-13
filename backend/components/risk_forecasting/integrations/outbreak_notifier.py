"""
Outbreak Notification Service.
Emits notifications to DAPH officials when district outbreak status transitions to active.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OutbreakNotifier:
    """
    Service for emitting outbreak notifications to DAPH officials.
    Integrates with the notification infrastructure to alert DAPH when
    district outbreak status changes from quiet to active.
    """

    def __init__(self):
        self._notification_handlers: List[callable] = []

    def register_handler(self, handler: callable):
        """Register a notification handler function."""
        if handler not in self._notification_handlers:
            self._notification_handlers.append(handler)

    def unregister_handler(self, handler: callable):
        """Unregister a notification handler function."""
        if handler in self._notification_handlers:
            self._notification_handlers.remove(handler)

    async def notify_outbreak_detected(
        self,
        disease: str,
        district: str,
        cases_count: int,
        deaths_count: int,
        year: int,
        month: int,
        metadata: Optional[Dict] = None
    ):
        """
        Emit outbreak detection notification to DAPH officials.

        Args:
            disease: Disease identifier (FMD or LSD)
            district: Sri Lankan administrative district name
            cases_count: Number of verified diagnostic cases
            deaths_count: Number of FMD/LSD deaths
            year: Calendar year
            month: Calendar month (1-12)
            metadata: Optional additional metadata
        """
        notification = {
            "event_type": "outbreak_detected",
            "disease": disease.upper(),
            "district": district,
            "cases_count": cases_count,
            "deaths_count": deaths_count,
            "year": year,
            "month": month,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "message": (
                f"Active {disease.upper()} outbreak detected in {district}. "
                f"{cases_count} verified case(s), {deaths_count} death(s) reported for {year}-{month:02d}."
            ),
            "action_link": f"/vet/forecasting?screen=outbreak-monitor&district={district}&disease={disease}"
        }

        logger.info(
            f"Outbreak notification: {disease.upper()} detected in {district} "
            f"({cases_count} cases, {deaths_count} deaths) for {year}-{month:02d}"
        )

        for handler in self._notification_handlers:
            try:
                await handler(notification)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")

    async def notify_status_change(
        self,
        disease: str,
        district: str,
        previous_status: float,
        current_status: float,
        year: int,
        month: int
    ):
        """
        Emit notification when outbreak status transitions from quiet to active.

        Args:
            disease: Disease identifier (FMD or LSD)
            district: Sri Lankan administrative district name
            previous_status: Previous outbreak status (0.0 or 1.0)
            current_status: Current outbreak status (0.0 or 1.0)
            year: Calendar year
            month: Calendar month (1-12)
        """
        if previous_status == 0.0 and current_status == 1.0:
            await self.notify_outbreak_detected(
                disease=disease,
                district=district,
                cases_count=0,
                deaths_count=0,
                year=year,
                month=month,
                metadata={"transition": "quiet_to_active"}
            )


outbreak_notifier = OutbreakNotifier()
