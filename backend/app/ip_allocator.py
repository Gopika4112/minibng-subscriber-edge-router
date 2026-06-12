from ipaddress import ip_network


class IPAllocator:
    """Allocates subscriber IP addresses from configured address pools."""

    def __init__(self, cidr: str = "10.10.0.0/24") -> None:
        self._network = ip_network(cidr)
        self._hosts = [
            str(host)
            for host in self._network.hosts()
            if host not in {self._network.network_address, self._network.broadcast_address}
        ]
        self._allocated: set[str] = set()

    def allocate(self) -> str:
        for host in self._hosts:
            if host not in self._allocated:
                self._allocated.add(host)
                return host

        raise RuntimeError("No available IP addresses")

    def release(self, ip_address: str) -> None:
        self._allocated.discard(str(ip_address))

    def allocated_ips(self) -> list[str]:
        return [host for host in self._hosts if host in self._allocated]
