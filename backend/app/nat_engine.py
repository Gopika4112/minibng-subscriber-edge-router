from ipaddress import ip_address

from backend.app.models import NATTranslation


FlowKey = tuple[str, int, str, int, str]
PublicKey = tuple[str, int, str]


class CGNATEngine:
    """Manages carrier-grade NAT translations for subscriber traffic."""

    def __init__(
        self,
        public_ips: list[str] | None = None,
        port_start: int = 30000,
        port_end: int = 40000,
    ) -> None:
        if public_ips is None:
            public_ips = ["100.64.0.10"]

        self._public_ips = [self._normalize_ip(ip) for ip in public_ips]
        self._validate_port(port_start)
        self._validate_port(port_end)
        if port_start > port_end:
            raise ValueError("Invalid NAT port range")

        self._port_start = port_start
        self._port_end = port_end
        self._flow_to_translation: dict[FlowKey, NATTranslation] = {}
        self._public_to_flow: dict[PublicKey, FlowKey] = {}

    def create_translation(
        self,
        private_ip: str,
        private_port: int,
        destination_ip: str,
        destination_port: int,
        protocol: str = "TCP",
    ) -> NATTranslation:
        normalized_private_ip = self._normalize_ip(private_ip)
        normalized_destination_ip = self._normalize_ip(destination_ip)
        self._validate_port(private_port)
        self._validate_port(destination_port)
        normalized_protocol = self._normalize_protocol(protocol)

        flow_key = (
            normalized_private_ip,
            private_port,
            normalized_destination_ip,
            destination_port,
            normalized_protocol,
        )
        existing_translation = self._flow_to_translation.get(flow_key)
        if existing_translation is not None:
            return existing_translation

        public_ip, public_port = self._allocate_public_endpoint(normalized_protocol)
        translation = NATTranslation(
            private_ip=normalized_private_ip,
            private_port=private_port,
            public_ip=public_ip,
            public_port=public_port,
            destination_ip=normalized_destination_ip,
            destination_port=destination_port,
            protocol=normalized_protocol,
            state="ACTIVE",
        )

        self._flow_to_translation[flow_key] = translation
        self._public_to_flow[(public_ip, public_port, normalized_protocol)] = flow_key
        return translation

    def list_translations(self) -> list[NATTranslation]:
        return list(self._flow_to_translation.values())

    def delete_translation(
        self,
        public_ip: str,
        public_port: int,
        protocol: str = "TCP",
    ) -> None:
        normalized_public_ip = self._normalize_ip(public_ip)
        self._validate_port(public_port)
        normalized_protocol = self._normalize_protocol(protocol)
        public_key = (normalized_public_ip, public_port, normalized_protocol)

        try:
            flow_key = self._public_to_flow.pop(public_key)
        except KeyError as exc:
            raise KeyError("NAT translation not found") from exc

        del self._flow_to_translation[flow_key]

    def clear(self) -> None:
        self._flow_to_translation.clear()
        self._public_to_flow.clear()

    def active_count(self) -> int:
        return len(self._flow_to_translation)

    def _allocate_public_endpoint(self, protocol: str) -> tuple[str, int]:
        for public_ip in self._public_ips:
            for public_port in range(self._port_start, self._port_end + 1):
                if (public_ip, public_port, protocol) not in self._public_to_flow:
                    return public_ip, public_port

        raise RuntimeError("No available NAT ports")

    @staticmethod
    def _normalize_ip(value: str) -> str:
        return str(ip_address(value))

    @staticmethod
    def _validate_port(port: int) -> None:
        if port < 1 or port > 65535:
            raise ValueError("Invalid port")

    @staticmethod
    def _normalize_protocol(protocol: str) -> str:
        normalized_protocol = protocol.upper()
        if normalized_protocol not in {"TCP", "UDP"}:
            raise ValueError("Unsupported protocol")
        return normalized_protocol
