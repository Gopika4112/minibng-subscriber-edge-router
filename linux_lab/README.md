# MiniBNG Linux Namespace Lab

This lab creates a small Linux networking topology that simulates three
broadband subscribers connected to a MiniBNG-style edge gateway.

It uses:

- Linux network namespaces for isolated subscriber hosts
- veth pairs for subscriber access links
- A Linux bridge as the MiniBNG edge/gateway

The bridge `minibng-br0` acts like the MiniBNG gateway and owns
`10.10.0.1/24`. Each subscriber namespace has its own veth interface and
default route through the bridge.

## Topology

```text
user101 10.10.0.101/24 ----\
user102 10.10.0.102/24 ----- minibng-br0 10.10.0.1/24
user103 10.10.0.103/24 ----/
```

## Commands

Set up the lab:

```bash
sudo bash linux_lab/setup_namespaces.sh
```

Test connectivity:

```bash
sudo bash linux_lab/test_connectivity.sh
```

Show topology details:

```bash
sudo bash linux_lab/show_topology.sh
```

Clean up the lab:

```bash
sudo bash linux_lab/cleanup_namespaces.sh
```

## Safety Note

These scripts create temporary Linux networking resources and should be run on
a development machine or VM. The setup script is idempotent: it runs cleanup
first, then recreates the namespaces, veth pairs, and bridge.
