from backend.app.models import Policy, PolicyDecision


class PolicyEngine:
    """Evaluates subscriber policies before packet forwarding decisions."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    def set_policy(
        self,
        subscriber_id: str,
        allowed: bool = True,
        allowed_protocols: list[str] | None = None,
        allowed_destination_ports: list[int] | None = None,
    ) -> Policy:
        normalized_protocols = self._normalize_protocols(allowed_protocols)
        normalized_ports = self._validate_ports(allowed_destination_ports)

        policy = Policy(
            subscriber_id=subscriber_id,
            allowed=allowed,
            allowed_protocols=normalized_protocols,
            allowed_destination_ports=normalized_ports,
        )
        self._policies[subscriber_id] = policy
        return policy

    def get_policy(self, subscriber_id: str) -> Policy:
        try:
            return self._policies[subscriber_id]
        except KeyError as exc:
            raise KeyError("Policy not found") from exc

    def delete_policy(self, subscriber_id: str) -> None:
        if subscriber_id not in self._policies:
            raise KeyError("Policy not found")

        del self._policies[subscriber_id]

    def list_policies(self) -> list[Policy]:
        return list(self._policies.values())

    def evaluate(
        self,
        subscriber_id: str,
        protocol: str,
        destination_port: int,
    ) -> PolicyDecision:
        normalized_protocol = self._normalize_protocol(protocol)
        self._validate_port(destination_port)

        policy = self._policies.get(subscriber_id)
        if policy is None:
            return PolicyDecision(
                allowed=True,
                reason="No policy configured; default allow",
            )

        if not policy.allowed:
            return PolicyDecision(
                allowed=False,
                reason="Subscriber policy blocks all traffic",
            )

        if (
            policy.allowed_protocols is not None
            and normalized_protocol not in policy.allowed_protocols
        ):
            return PolicyDecision(
                allowed=False,
                reason="Protocol not allowed by policy",
            )

        if (
            policy.allowed_destination_ports is not None
            and destination_port not in policy.allowed_destination_ports
        ):
            return PolicyDecision(
                allowed=False,
                reason="Destination port not allowed by policy",
            )

        return PolicyDecision(allowed=True, reason="Policy allows traffic")

    def _normalize_protocols(
        self,
        protocols: list[str] | None,
    ) -> list[str] | None:
        if protocols is None:
            return None

        return [self._normalize_protocol(protocol) for protocol in protocols]

    def _validate_ports(self, ports: list[int] | None) -> list[int] | None:
        if ports is None:
            return None

        for port in ports:
            self._validate_port(port)
        return ports

    @staticmethod
    def _normalize_protocol(protocol: str) -> str:
        normalized_protocol = protocol.upper()
        if normalized_protocol not in {"TCP", "UDP"}:
            raise ValueError("Unsupported protocol")
        return normalized_protocol

    @staticmethod
    def _validate_port(port: int) -> None:
        if port < 1 or port > 65535:
            raise ValueError("Invalid port")
