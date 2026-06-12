from backend.app.ip_allocator import IPAllocator
from backend.app.models import Subscriber


class SubscriberManager:
    """Coordinates subscriber session state for the MiniBNG simulator."""

    def __init__(self, ip_allocator: IPAllocator | None = None) -> None:
        self._ip_allocator = ip_allocator or IPAllocator()
        self._subscribers: dict[str, Subscriber] = {}

    def create_subscriber(self, subscriber_id: str, plan: str = "basic") -> Subscriber:
        if subscriber_id in self._subscribers:
            raise ValueError("Subscriber already exists")

        subscriber = Subscriber(
            subscriber_id=subscriber_id,
            ip_address=self._ip_allocator.allocate(),
            plan=plan,
            status="ACTIVE",
        )
        self._subscribers[subscriber_id] = subscriber
        return subscriber

    def list_subscribers(self) -> list[Subscriber]:
        return list(self._subscribers.values())

    def get_subscriber(self, subscriber_id: str) -> Subscriber:
        try:
            return self._subscribers[subscriber_id]
        except KeyError as exc:
            raise KeyError("Subscriber not found") from exc

    def block_subscriber(self, subscriber_id: str) -> Subscriber:
        subscriber = self.get_subscriber(subscriber_id)
        subscriber.status = "BLOCKED"
        return subscriber

    def unblock_subscriber(self, subscriber_id: str) -> Subscriber:
        subscriber = self.get_subscriber(subscriber_id)
        subscriber.status = "ACTIVE"
        return subscriber

    def delete_subscriber(self, subscriber_id: str) -> None:
        subscriber = self.get_subscriber(subscriber_id)
        self._ip_allocator.release(subscriber.ip_address)
        del self._subscribers[subscriber_id]
