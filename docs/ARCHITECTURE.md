# MiniBNG Architecture

MiniBNG is organized as a small control-plane and packet-decision simulator.
Each module owns one clear networking responsibility, while the FastAPI app and
CLI expose those capabilities for demos and tests.

## SubscriberManager

`SubscriberManager` stores subscriber sessions in memory. A subscriber has an
ID, assigned private IP address, plan, and status. The manager supports create,
list, lookup, block, unblock, and delete operations.

When a subscriber is created, it asks `IPAllocator` for a private address. When
a subscriber is deleted, it releases that address back to the pool.

## IPAllocator

`IPAllocator` allocates usable host IP addresses from a configured CIDR block.
The default pool is `10.10.0.0/24`.

It avoids the network and broadcast addresses, tracks allocated addresses, and
reuses released addresses. This gives MiniBNG realistic subscriber private IP
assignment behavior without needing DHCP or PPPoE.

## PolicyEngine

`PolicyEngine` evaluates subscriber-aware traffic policy before NAT and routing.
Policies are stored by subscriber ID and can:

- Allow or block all traffic for a subscriber
- Restrict traffic to selected protocols
- Restrict traffic to selected destination ports

If no policy exists, traffic is allowed by default. Protocols are normalized to
uppercase, and only TCP and UDP are valid.

## CGNATEngine

`CGNATEngine` simulates carrier-grade NAT by mapping private subscriber flows to
a shared public IP and public port.

A private flow is identified by:

```text
private_ip, private_port, destination_ip, destination_port, protocol
```

If the same flow is seen again, MiniBNG returns the existing translation instead
of creating a duplicate. Public ports are allocated sequentially across the
configured public IP pool.

## RouteTable

`RouteTable` stores static routes and performs longest-prefix match lookups.
Prefixes and destination IPs are validated with Python's `ipaddress` module.

If multiple routes match a destination, the most specific prefix wins. For
example, `10.10.1.0/24` beats `10.10.0.0/16` for destination `10.10.1.5`.

## PacketSimulator

`PacketSimulator` is the core explainability layer. It connects subscriber
state, policy evaluation, NAT, route lookup, and metrics into one packet
decision pipeline.

The six pipeline steps are:

```text
subscriber_lookup
subscriber_status
policy_check
nat_translation
route_lookup
forwarding_decision
```

Each step produces a trace entry with:

- `step`
- `status`: `PASS`, `FAIL`, or `SKIPPED`
- `reason`
- optional metadata

If an early step fails, later steps are marked `SKIPPED`. This makes packet
drops easy to debug and easy to explain in an interview.

## MetricsStore

`MetricsStore` keeps router-style counters in memory:

- Total packets
- Forwarded packets
- Dropped packets
- Drops by reason

The metrics endpoint also combines live counts from other modules, including
active NAT translations, active/blocked subscribers, and installed routes.

## CLI

The CLI in `cli/minibng_cli.py` is a Typer application that talks to the FastAPI
backend over HTTP using `requests`. It does not import backend classes directly.

It provides router-style commands for:

- Showing subscribers, routes, NAT, policies, and metrics
- Adding/deleting subscribers, routes, and policies
- Blocking/unblocking subscribers
- Simulating packets
- Running one-shot demo flows

Rich tables make output readable during demos.
