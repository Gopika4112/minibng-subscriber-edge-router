from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from backend.app.models import Route, RouteLookupResult


IPNetwork = IPv4Network | IPv6Network


class RouteTable:
    """Stores routes and performs destination lookup decisions."""

    def __init__(self) -> None:
        self._routes: dict[str, tuple[IPNetwork, Route]] = {}

    def add_route(
        self,
        prefix: str,
        interface: str,
        next_hop: str | None = None,
    ) -> Route:
        network = ip_network(prefix)
        normalized_prefix = str(network)

        if normalized_prefix in self._routes:
            raise ValueError("Route already exists")

        route = Route(
            prefix=normalized_prefix,
            next_hop=next_hop,
            interface=interface,
        )
        self._routes[normalized_prefix] = (network, route)
        return route

    def delete_route(self, prefix: str) -> None:
        network = ip_network(prefix)
        normalized_prefix = str(network)

        if normalized_prefix not in self._routes:
            raise KeyError("Route not found")

        del self._routes[normalized_prefix]

    def list_routes(self) -> list[Route]:
        return [route for _, route in self._routes.values()]

    def lookup(self, destination_ip: str) -> RouteLookupResult:
        destination = ip_address(destination_ip)
        matching_routes = [
            (network, route)
            for network, route in self._routes.values()
            if destination in network
        ]

        if not matching_routes:
            raise KeyError("No matching route found")

        _, route = max(matching_routes, key=lambda item: item[0].prefixlen)
        return RouteLookupResult(
            destination_ip=str(destination),
            matched_prefix=route.prefix,
            next_hop=route.next_hop,
            interface=route.interface,
        )
