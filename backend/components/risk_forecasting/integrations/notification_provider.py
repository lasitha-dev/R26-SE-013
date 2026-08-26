"""
Notification Provider Interface & Mock Implementation (Phase 4).

Defines the NotificationProvider protocol, delivery payloads, result DTOs,
and MockNotificationProvider implementation.

PRODUCTION REPLACEMENT PATH:
NotificationProvider -> future SharedFarmerDashboardNotificationAdapter or SMS/Push gateway adapter.
"""

from datetime import datetime, timezone
from typing import Callable, Optional, Protocol, Set
import uuid

from pydantic import BaseModel, Field


class ProviderDeliveryPayload(BaseModel):
    """Immutable non-sensitive delivery payload passed to notification provider."""
    delivery_id: str = Field(..., description="Unique delivery item ID.")
    batch_id: str = Field(..., description="Parent notification batch ID.")
    advisory_id: str = Field(..., description="Referenced approved advisory ID.")
    forecast_id: str = Field(..., description="Referenced immutable forecast decision record ID.")
    recipient_id: str = Field(..., description="Target recipient or farm ID.")
    resolved_message: str = Field(..., description="Frozen final resolved message text.")


class ProviderDeliveryResult(BaseModel):
    """Structured result returned by notification provider execution."""
    success: bool = Field(..., description="True if delivery succeeded.")
    provider_reference: Optional[str] = Field(default=None, description="Provider transaction/dispatch reference.")
    provider_status: str = Field(..., description="Raw provider status label (e.g. DELIVERED, FAILED).")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code if delivery failed.")
    error_message: Optional[str] = Field(default=None, description="Human-readable error description if delivery failed.")
    attempted_at: str = Field(..., description="Timezone-aware ISO 8601 UTC execution timestamp.")


class NotificationProvider(Protocol):
    """Protocol contract for notification providers."""
    provider_name: str

    def send(self, payload: ProviderDeliveryPayload) -> ProviderDeliveryResult:
        ...


class MockNotificationProvider:
    """
    Mock implementation of NotificationProvider.

    IMPORTANT SAFETY & OPERATIONAL NOTICE:
    - Performs NO real delivery, network calls, or external service interactions.
    - SUCCEEDED status in standalone mock mode represents simulated provider success ONLY.
    - It does NOT mean the farmer received, opened, read, or acknowledged a message.
    - provider_name ('MockNotificationProvider') and provider_status ('SIMULATED_SUCCESS') clearly identify mock execution.
    - Configurable simulated failures and exceptions by recipient ID for testing outbox retry behavior.
    - Deterministic provider references via optional ref_generator.
    """

    def __init__(
        self,
        failed_recipient_ids: Optional[Set[str]] = None,
        raise_exception_ids: Optional[Set[str]] = None,
        ref_generator: Optional[Callable[[], str]] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.provider_name = "MockNotificationProvider"
        self.failed_recipient_ids = set(failed_recipient_ids) if failed_recipient_ids else set()
        self.raise_exception_ids = set(raise_exception_ids) if raise_exception_ids else set()
        self.ref_generator = ref_generator or (lambda: f"mock_ref_{uuid.uuid4().hex[:8]}")
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def send(self, payload: ProviderDeliveryPayload) -> ProviderDeliveryResult:
        now_iso = self.clock().isoformat()

        if payload.recipient_id in self.raise_exception_ids:
            raise RuntimeError(f"Mock network exception for recipient '{payload.recipient_id}'")

        if payload.recipient_id in self.failed_recipient_ids:
            return ProviderDeliveryResult(
                success=False,
                provider_reference=None,
                provider_status="FAILED",
                error_code="MOCK_DELIVERY_FAILURE",
                error_message=f"Mock provider simulated delivery failure for recipient '{payload.recipient_id}'",
                attempted_at=now_iso,
            )

        return ProviderDeliveryResult(
            success=True,
            provider_reference=self.ref_generator(),
            provider_status="SIMULATED_SUCCESS",
            error_code=None,
            error_message=None,
            attempted_at=now_iso,
        )


# Default Singleton Instance
mock_notification_provider = MockNotificationProvider()
