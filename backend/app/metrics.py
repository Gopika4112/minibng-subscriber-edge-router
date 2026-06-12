from backend.app.models import MetricsSnapshot


class MetricsStore:
    """Collects runtime counters and observability data for MiniBNG."""

    def __init__(self) -> None:
        self.packets_total = 0
        self.packets_forwarded = 0
        self.packets_dropped = 0
        self.drops_by_reason: dict[str, int] = {}

    def record_forwarded(self) -> None:
        self.packets_total += 1
        self.packets_forwarded += 1

    def record_dropped(self, reason: str) -> None:
        self.packets_total += 1
        self.packets_dropped += 1
        self.drops_by_reason[reason] = self.drops_by_reason.get(reason, 0) + 1

    def reset(self) -> None:
        self.packets_total = 0
        self.packets_forwarded = 0
        self.packets_dropped = 0
        self.drops_by_reason = {}

    def snapshot(
        self,
        nat_translations_active: int,
        subscribers_active: int,
        subscribers_blocked: int,
        routes_installed: int,
    ) -> MetricsSnapshot:
        return MetricsSnapshot(
            packets_total=self.packets_total,
            packets_forwarded=self.packets_forwarded,
            packets_dropped=self.packets_dropped,
            drops_by_reason=dict(self.drops_by_reason),
            nat_translations_active=nat_translations_active,
            subscribers_active=subscribers_active,
            subscribers_blocked=subscribers_blocked,
            routes_installed=routes_installed,
        )
