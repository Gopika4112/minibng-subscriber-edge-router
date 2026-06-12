# MiniBNG Demo Guide

This guide shows how to run the MiniBNG interview demo from a clean terminal.

## Start the Backend

From the repository root:

```bash
uvicorn backend.app.main:app --reload --port 8001
```

The CLI uses `http://127.0.0.1:8001` by default. To point it elsewhere, set
`MINIBNG_API_URL`.

## Prepare Demo State

Run:

```bash
python3 cli/minibng_cli.py demo seed
```

This command:

- Resets packet/drop metrics
- Clears the NAT table
- Ensures subscriber `user-demo` exists with plan `100Mbps`
- Ensures a default route exists through `core0`
- Sets a policy allowing TCP/UDP traffic only on ports `53`, `80`, and `443`

The command is idempotent. If the subscriber or route already exists, it
continues without crashing.

## Run the Full Demo

Run:

```bash
python3 cli/minibng_cli.py demo run
```

This performs the same setup as `demo seed`, then simulates three packets and
prints the decision trace for each packet.

## Demo Packets

### 1. UDP DNS Packet

```text
subscriber_id: user-demo
source_port: 45677
destination_ip: 8.8.8.8
destination_port: 53
protocol: UDP
```

This packet is expected to be `FORWARDED`.

It demonstrates subscriber lookup, policy allow, NAT translation, default route
lookup, and final forwarding.

### 2. TCP Web Packet

```text
subscriber_id: user-demo
source_port: 45678
destination_ip: 93.184.216.34
destination_port: 80
protocol: TCP
```

This packet is expected to be `FORWARDED`.

It demonstrates that the subscriber policy allows TCP web traffic and that a new
CGNAT translation is allocated for a different private flow.

### 3. TCP SSH Packet

```text
subscriber_id: user-demo
source_port: 45679
destination_ip: 1.1.1.1
destination_port: 22
protocol: TCP
```

This packet is expected to be `DROPPED`.

It demonstrates subscriber-aware policy enforcement. Port `22` is not in the
allowed destination port list, so NAT and route lookup are skipped.

## Metrics

At the end of `demo run`, MiniBNG prints router-style metrics.

For the demo flow, the expected summary is:

```text
packets_total: 3
packets_forwarded: 2
packets_dropped: 1
drops_by_reason: policy_blocked = 1
```

The metrics also show live control-plane state such as active NAT translations,
active subscribers, blocked subscribers, and installed routes.

## Interview Explanation

MiniBNG simulates the decision path of a broadband edge router. A packet enters
from a subscriber, the system verifies subscriber state, checks policy, creates
a CGNAT mapping, performs longest-prefix route lookup, and then either forwards
or drops the packet.

The key design goal is explainability. Instead of returning only `FORWARDED` or
`DROPPED`, MiniBNG returns a structured trace showing every stage of the
pipeline. This makes it useful for understanding control plane/data plane
interaction, NAT behavior, route lookup, policy enforcement, and operational
debugging.
