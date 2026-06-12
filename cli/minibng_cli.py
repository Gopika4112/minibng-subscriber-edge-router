import json
import os
from typing import Any

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


DEFAULT_API_URL = "http://127.0.0.1:8001"
BACKEND_START_COMMAND = "uvicorn backend.app.main:app --reload --port 8001"

console = Console()
app = typer.Typer(help="MiniBNG router-style command-line interface.")
show_app = typer.Typer(help="Show MiniBNG state.")
add_app = typer.Typer(help="Add MiniBNG objects.")
delete_app = typer.Typer(help="Delete MiniBNG objects.")
block_app = typer.Typer(help="Block subscribers.")
unblock_app = typer.Typer(help="Unblock subscribers.")
set_app = typer.Typer(help="Set MiniBNG configuration.")
simulate_app = typer.Typer(help="Run packet simulations.")
reset_app = typer.Typer(help="Reset MiniBNG counters or state.")
demo_app = typer.Typer(help="Run MiniBNG demo scenarios.")

app.add_typer(show_app, name="show")
app.add_typer(add_app, name="add")
app.add_typer(delete_app, name="delete")
app.add_typer(block_app, name="block")
app.add_typer(unblock_app, name="unblock")
app.add_typer(set_app, name="set")
app.add_typer(simulate_app, name="simulate")
app.add_typer(reset_app, name="reset")
app.add_typer(demo_app, name="demo")


def api_url() -> str:
    return os.getenv("MINIBNG_API_URL", DEFAULT_API_URL).rstrip("/")


def api_request(
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> Any:
    response = send_api_request(method, path, json_body)

    if response.status_code >= 400:
        print_api_error(response)
        raise typer.Exit(code=1)

    return response_payload(response)


def send_api_request(
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=f"{api_url()}{path}",
            json=json_body,
            timeout=5,
        )
    except requests.exceptions.ConnectionError:
        console.print(
            "[bold red]MiniBNG backend is not reachable.[/] "
            f"Start it with: [bold]{BACKEND_START_COMMAND}[/]"
        )
        raise typer.Exit(code=1) from None
    except requests.exceptions.RequestException as exc:
        console.print(f"[bold red]Request failed:[/] {exc}")
        raise typer.Exit(code=1) from None


def response_payload(response: requests.Response) -> Any:
    if not response.content:
        return None

    try:
        return response.json()
    except ValueError:
        return response.text


def api_request_allowing_error(
    method: str,
    path: str,
    json_body: dict[str, Any] | None,
    allowed_status: int,
    allowed_detail: str,
) -> Any:
    response = send_api_request(method, path, json_body)
    if response.status_code < 400:
        return response_payload(response)

    if response.status_code == allowed_status and error_detail(response) == allowed_detail:
        return None

    print_api_error(response)
    raise typer.Exit(code=1)


def error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        detail = body.get("detail", body) if isinstance(body, dict) else body
    except ValueError:
        detail = response.text

    if not isinstance(detail, str):
        return json.dumps(detail)
    return detail


def print_api_error(response: requests.Response) -> None:
    console.print(f"[bold red]API error {response.status_code}:[/] {error_detail(response)}")


def value_text(value: Any, empty: str = "-") -> str:
    if value is None:
        return empty
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else empty
    return str(value)


def endpoint_text(ip_address: str, port: int) -> str:
    return f"{ip_address}:{port}"


def print_metrics(metrics: dict[str, Any]) -> None:
    table = Table(title="MiniBNG Metrics")
    table.add_column("metric", style="cyan")
    table.add_column("value", justify="right")

    for key in (
        "packets_total",
        "packets_forwarded",
        "packets_dropped",
        "nat_translations_active",
        "subscribers_active",
        "subscribers_blocked",
        "routes_installed",
    ):
        table.add_row(key, str(metrics[key]))

    console.print(table)

    drops_by_reason = metrics["drops_by_reason"]
    if drops_by_reason:
        drop_table = Table(title="Drops by Reason")
        drop_table.add_column("reason", style="red")
        drop_table.add_column("count", justify="right")
        for reason, count in drops_by_reason.items():
            drop_table.add_row(reason, str(count))
        console.print(drop_table)


def print_packet_response(response: dict[str, Any]) -> None:
    decision_color = "green" if response["decision"] == "FORWARDED" else "red"
    console.print(
        Panel.fit(
            f"[bold {decision_color}]{response['decision']}[/]",
            title="Packet Decision",
        )
    )

    if response["decision"] == "FORWARDED":
        console.print(f"Original source: {response['original_source_ip']}")
        console.print(
            "Translated source: "
            f"{response['translated_source_ip']}:{response['translated_source_port']}"
        )
        console.print(f"Matched prefix: {response['matched_prefix']}")
        console.print(f"Outgoing interface: {response['outgoing_interface']}")
        console.print(f"Next hop: {value_text(response['next_hop'])}")

    trace_table = Table(title="Decision Trace")
    trace_table.add_column("step", style="cyan")
    trace_table.add_column("status")
    trace_table.add_column("reason")

    for step in response["trace"]:
        trace_table.add_row(step["step"], step["status"], step["reason"])

    console.print(trace_table)


def seed_demo_environment(print_success: bool = True) -> None:
    api_request("POST", "/metrics/reset")
    api_request("DELETE", "/nat")
    api_request_allowing_error(
        "POST",
        "/subscribers",
        {"subscriber_id": "user-demo", "plan": "100Mbps"},
        allowed_status=400,
        allowed_detail="Subscriber already exists",
    )
    api_request("POST", "/subscribers/user-demo/unblock")
    api_request_allowing_error(
        "POST",
        "/routes",
        {
            "prefix": "0.0.0.0/0",
            "next_hop": "192.168.1.1",
            "interface": "core0",
        },
        allowed_status=400,
        allowed_detail="Route already exists",
    )
    api_request(
        "POST",
        "/policies",
        {
            "subscriber_id": "user-demo",
            "allowed": True,
            "allowed_protocols": ["TCP", "UDP"],
            "allowed_destination_ports": [53, 80, 443],
        },
    )

    if print_success:
        console.print("[green]Demo environment ready[/]")


@show_app.command("subscribers")
def show_subscribers() -> None:
    """Display subscribers."""
    subscribers = api_request("GET", "/subscribers")
    table = Table(title="Subscribers")
    table.add_column("subscriber_id", style="cyan")
    table.add_column("ip_address")
    table.add_column("plan")
    table.add_column("status")

    for subscriber in subscribers:
        table.add_row(
            subscriber["subscriber_id"],
            subscriber["ip_address"],
            subscriber["plan"],
            subscriber["status"],
        )

    console.print(table)


@show_app.command("routes")
def show_routes() -> None:
    """Display installed routes."""
    routes = api_request("GET", "/routes")
    table = Table(title="Routes")
    table.add_column("prefix", style="cyan")
    table.add_column("next_hop")
    table.add_column("interface")

    for route in routes:
        table.add_row(
            route["prefix"],
            value_text(route["next_hop"]),
            route["interface"],
        )

    console.print(table)


@show_app.command("nat")
def show_nat() -> None:
    """Display active CGNAT translations."""
    translations = api_request("GET", "/nat")
    table = Table(title="NAT Translations")
    table.add_column("private")
    table.add_column("public", style="cyan")
    table.add_column("destination")
    table.add_column("protocol")
    table.add_column("state")

    for translation in translations:
        table.add_row(
            endpoint_text(translation["private_ip"], translation["private_port"]),
            endpoint_text(translation["public_ip"], translation["public_port"]),
            endpoint_text(
                translation["destination_ip"],
                translation["destination_port"],
            ),
            translation["protocol"],
            translation["state"],
        )

    console.print(table)


@show_app.command("policies")
def show_policies() -> None:
    """Display subscriber policies."""
    policies = api_request("GET", "/policies")
    table = Table(title="Policies")
    table.add_column("subscriber_id", style="cyan")
    table.add_column("allowed")
    table.add_column("allowed_protocols")
    table.add_column("allowed_destination_ports")

    for policy in policies:
        table.add_row(
            policy["subscriber_id"],
            value_text(policy["allowed"]),
            value_text(policy["allowed_protocols"], empty="any"),
            value_text(policy["allowed_destination_ports"], empty="any"),
        )

    console.print(table)


@show_app.command("metrics")
def show_metrics() -> None:
    """Display router-style counters."""
    metrics = api_request("GET", "/metrics")
    print_metrics(metrics)


@add_app.command("subscriber")
def add_subscriber(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
    plan: str = typer.Option("basic", "--plan", help="Subscriber plan."),
) -> None:
    """Add a subscriber."""
    subscriber = api_request(
        "POST",
        "/subscribers",
        {"subscriber_id": subscriber_id, "plan": plan},
    )
    console.print(
        f"[green]Subscriber added:[/] {subscriber['subscriber_id']} "
        f"({subscriber['ip_address']})"
    )


@delete_app.command("subscriber")
def delete_subscriber(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
) -> None:
    """Delete a subscriber."""
    api_request("DELETE", f"/subscribers/{subscriber_id}")
    console.print(f"[green]Subscriber deleted:[/] {subscriber_id}")


@block_app.command("subscriber")
def block_subscriber(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
) -> None:
    """Block a subscriber."""
    subscriber = api_request("POST", f"/subscribers/{subscriber_id}/block")
    console.print(f"[yellow]Subscriber blocked:[/] {subscriber['subscriber_id']}")


@unblock_app.command("subscriber")
def unblock_subscriber(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
) -> None:
    """Unblock a subscriber."""
    subscriber = api_request("POST", f"/subscribers/{subscriber_id}/unblock")
    console.print(f"[green]Subscriber unblocked:[/] {subscriber['subscriber_id']}")


@add_app.command("route")
def add_route(
    prefix: str = typer.Argument(..., help="Route prefix, for example 0.0.0.0/0."),
    interface: str = typer.Option(..., "--interface", help="Outgoing interface."),
    next_hop: str | None = typer.Option(None, "--next-hop", help="Next-hop IP."),
) -> None:
    """Add a static route."""
    payload = {"prefix": prefix, "interface": interface, "next_hop": next_hop}
    route = api_request("POST", "/routes", payload)
    console.print(f"[green]Route added:[/] {route['prefix']} via {route['interface']}")


@delete_app.command("route")
def delete_route(
    prefix: str = typer.Argument(..., help="Route prefix."),
) -> None:
    """Delete a static route."""
    api_request("DELETE", f"/routes/{prefix}")
    console.print(f"[green]Route deleted:[/] {prefix}")


@set_app.command("policy")
def set_policy(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
    allowed: bool = typer.Option(
        True,
        "--allowed/--blocked",
        help="Allow or block all traffic for this subscriber.",
    ),
    protocol: list[str] | None = typer.Option(
        None,
        "--protocol",
        help="Allowed protocol. Repeat for multiple protocols.",
    ),
    port: list[int] | None = typer.Option(
        None,
        "--port",
        help="Allowed destination port. Repeat for multiple ports.",
    ),
) -> None:
    """Set a subscriber traffic policy."""
    policy = api_request(
        "POST",
        "/policies",
        {
            "subscriber_id": subscriber_id,
            "allowed": allowed,
            "allowed_protocols": protocol,
            "allowed_destination_ports": port,
        },
    )
    console.print(f"[green]Policy set:[/] {policy['subscriber_id']}")


@delete_app.command("policy")
def delete_policy(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
) -> None:
    """Delete a subscriber policy."""
    api_request("DELETE", f"/policies/{subscriber_id}")
    console.print(f"[green]Policy deleted:[/] {subscriber_id}")


@simulate_app.command("packet")
def simulate_packet(
    subscriber_id: str = typer.Argument(..., help="Subscriber ID."),
    source_port: int = typer.Option(..., "--source-port", help="Source port."),
    destination_ip: str = typer.Option(..., "--destination-ip", help="Destination IP."),
    destination_port: int = typer.Option(
        ...,
        "--destination-port",
        help="Destination port.",
    ),
    protocol: str = typer.Option("TCP", "--protocol", help="Protocol."),
) -> None:
    """Simulate a subscriber packet through the MiniBNG pipeline."""
    response = api_request(
        "POST",
        "/simulate-packet",
        {
            "subscriber_id": subscriber_id,
            "source_port": source_port,
            "destination_ip": destination_ip,
            "destination_port": destination_port,
            "protocol": protocol,
        },
    )
    print_packet_response(response)


@reset_app.command("metrics")
def reset_metrics() -> None:
    """Reset packet and drop counters."""
    api_request("POST", "/metrics/reset")
    console.print("[green]Metrics reset[/]")


@demo_app.command("seed")
def demo_seed() -> None:
    """Prepare a clean MiniBNG demo scenario."""
    seed_demo_environment()


@demo_app.command("run")
def demo_run() -> None:
    """Run a complete MiniBNG demo flow."""
    seed_demo_environment(print_success=False)
    console.print("[green]Demo environment ready[/]")

    demo_packets = [
        (
            "UDP DNS packet",
            "FORWARDED",
            {
                "subscriber_id": "user-demo",
                "source_port": 45677,
                "destination_ip": "8.8.8.8",
                "destination_port": 53,
                "protocol": "UDP",
            },
        ),
        (
            "TCP web packet",
            "FORWARDED",
            {
                "subscriber_id": "user-demo",
                "source_port": 45678,
                "destination_ip": "93.184.216.34",
                "destination_port": 80,
                "protocol": "TCP",
            },
        ),
        (
            "TCP SSH packet",
            "DROPPED",
            {
                "subscriber_id": "user-demo",
                "source_port": 45679,
                "destination_ip": "1.1.1.1",
                "destination_port": 22,
                "protocol": "TCP",
            },
        ),
    ]

    for label, expected_decision, payload in demo_packets:
        console.rule(label)
        response = api_request("POST", "/simulate-packet", payload)
        console.print(
            f"[bold]{label}[/]: {response['decision']} "
            f"(expected {expected_decision})"
        )
        print_packet_response(response)

    console.rule("Final Metrics")
    print_metrics(api_request("GET", "/metrics"))


if __name__ == "__main__":
    app()
