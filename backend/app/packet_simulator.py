from typing import Any

from backend.app.models import (
    NATTranslation,
    PacketSimulationRequest,
    PacketSimulationResponse,
    RouteLookupResult,
    TraceStep,
)
from backend.app.metrics import MetricsStore
from backend.app.nat_engine import CGNATEngine
from backend.app.policy_engine import PolicyEngine
from backend.app.route_table import RouteTable
from backend.app.subscriber_manager import SubscriberManager


class PacketSimulator:
    """Runs a simulated subscriber packet through the MiniBNG decision pipeline."""

    def __init__(
        self,
        subscriber_manager: SubscriberManager,
        nat_engine: CGNATEngine,
        route_table: RouteTable,
        policy_engine: PolicyEngine,
        metrics_store: MetricsStore,
    ) -> None:
        self._subscriber_manager = subscriber_manager
        self._nat_engine = nat_engine
        self._route_table = route_table
        self._policy_engine = policy_engine
        self._metrics_store = metrics_store

    def simulate(
        self,
        request: PacketSimulationRequest,
    ) -> PacketSimulationResponse:
        trace: list[TraceStep] = []
        protocol = request.protocol.upper()

        try:
            subscriber = self._subscriber_manager.get_subscriber(request.subscriber_id)
        except KeyError:
            trace.append(
                self._step(
                    "subscriber_lookup",
                    "FAIL",
                    "Subscriber not found",
                )
            )
            self._skip_remaining(
                trace,
                [
                    ("subscriber_status", "Subscriber lookup failed"),
                    ("policy_check", "Subscriber lookup failed"),
                    ("nat_translation", "Subscriber lookup failed"),
                    ("route_lookup", "Subscriber lookup failed"),
                    ("forwarding_decision", "Subscriber lookup failed"),
                ],
            )
            self._metrics_store.record_dropped("subscriber_not_found")
            return self._response(
                request=request,
                protocol=protocol,
                decision="DROPPED",
                original_source_ip=None,
                trace=trace,
            )

        trace.append(
            self._step(
                "subscriber_lookup",
                "PASS",
                "Subscriber found",
                {
                    "subscriber_id": subscriber.subscriber_id,
                    "ip_address": subscriber.ip_address,
                },
            )
        )

        if subscriber.status == "BLOCKED":
            trace.append(
                self._step(
                    "subscriber_status",
                    "FAIL",
                    "Subscriber is blocked",
                    {"status": subscriber.status},
                )
            )
            self._skip_remaining(
                trace,
                [
                    ("policy_check", "Subscriber is blocked"),
                    ("nat_translation", "Subscriber is blocked"),
                    ("route_lookup", "Subscriber is blocked"),
                    ("forwarding_decision", "Subscriber is blocked"),
                ],
            )
            self._metrics_store.record_dropped("subscriber_blocked")
            return self._response(
                request=request,
                protocol=protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                trace=trace,
            )

        trace.append(
            self._step(
                "subscriber_status",
                "PASS",
                "Subscriber is active",
                {"status": subscriber.status},
            )
        )

        try:
            policy_decision = self._policy_engine.evaluate(
                subscriber_id=subscriber.subscriber_id,
                protocol=request.protocol,
                destination_port=request.destination_port,
            )
        except ValueError as exc:
            trace.append(
                self._step(
                    "policy_check",
                    "FAIL",
                    str(exc),
                )
            )
            self._skip_remaining(
                trace,
                [
                    ("nat_translation", "Policy check failed"),
                    ("route_lookup", "Policy check failed"),
                    ("forwarding_decision", "Policy check failed"),
                ],
            )
            self._metrics_store.record_dropped("policy_error")
            return self._response(
                request=request,
                protocol=protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                trace=trace,
            )

        if not policy_decision.allowed:
            trace.append(
                self._step(
                    "policy_check",
                    "FAIL",
                    policy_decision.reason,
                )
            )
            self._skip_remaining(
                trace,
                [
                    ("nat_translation", "Policy blocked packet"),
                    ("route_lookup", "Policy blocked packet"),
                    ("forwarding_decision", "Policy blocked packet"),
                ],
            )
            self._metrics_store.record_dropped("policy_blocked")
            return self._response(
                request=request,
                protocol=protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                trace=trace,
            )

        trace.append(
            self._step(
                "policy_check",
                "PASS",
                policy_decision.reason,
            )
        )

        try:
            translation = self._nat_engine.create_translation(
                private_ip=subscriber.ip_address,
                private_port=request.source_port,
                destination_ip=request.destination_ip,
                destination_port=request.destination_port,
                protocol=request.protocol,
            )
        except (ValueError, RuntimeError) as exc:
            trace.append(
                self._step(
                    "nat_translation",
                    "FAIL",
                    str(exc),
                )
            )
            self._skip_remaining(
                trace,
                [
                    ("route_lookup", "NAT translation failed"),
                    ("forwarding_decision", "NAT translation failed"),
                ],
            )
            self._metrics_store.record_dropped("nat_translation_failed")
            return self._response(
                request=request,
                protocol=protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                trace=trace,
            )

        trace.append(
            self._step(
                "nat_translation",
                "PASS",
                "NAT translation created",
                {
                    "public_ip": translation.public_ip,
                    "public_port": translation.public_port,
                    "protocol": translation.protocol,
                },
            )
        )

        try:
            route = self._route_table.lookup(request.destination_ip)
        except KeyError:
            trace.append(
                self._step(
                    "route_lookup",
                    "FAIL",
                    "No matching route found",
                )
            )
            self._skip_remaining(
                trace,
                [("forwarding_decision", "Route lookup failed")],
            )
            self._metrics_store.record_dropped("route_not_found")
            return self._response(
                request=request,
                protocol=translation.protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                translation=translation,
                trace=trace,
            )
        except ValueError as exc:
            trace.append(
                self._step(
                    "route_lookup",
                    "FAIL",
                    str(exc),
                )
            )
            self._skip_remaining(
                trace,
                [("forwarding_decision", "Route lookup failed")],
            )
            self._metrics_store.record_dropped("route_not_found")
            return self._response(
                request=request,
                protocol=translation.protocol,
                decision="DROPPED",
                original_source_ip=subscriber.ip_address,
                translation=translation,
                trace=trace,
            )

        trace.append(
            self._step(
                "route_lookup",
                "PASS",
                "Route found",
                {
                    "matched_prefix": route.matched_prefix,
                    "interface": route.interface,
                    "next_hop": route.next_hop,
                },
            )
        )
        trace.append(
            self._step(
                "forwarding_decision",
                "PASS",
                "Packet forwarded",
            )
        )

        self._metrics_store.record_forwarded()
        return self._response(
            request=request,
            protocol=translation.protocol,
            decision="FORWARDED",
            original_source_ip=subscriber.ip_address,
            translation=translation,
            route=route,
            trace=trace,
        )

    @staticmethod
    def _step(
        step: str,
        status: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceStep:
        return TraceStep(
            step=step,
            status=status,
            reason=reason,
            metadata=metadata or {},
        )

    def _skip_remaining(
        self,
        trace: list[TraceStep],
        skipped_steps: list[tuple[str, str]],
    ) -> None:
        for step, reason in skipped_steps:
            trace.append(self._step(step, "SKIPPED", reason))

    @staticmethod
    def _response(
        request: PacketSimulationRequest,
        protocol: str,
        decision: str,
        original_source_ip: str | None,
        trace: list[TraceStep],
        translation: NATTranslation | None = None,
        route: RouteLookupResult | None = None,
    ) -> PacketSimulationResponse:
        return PacketSimulationResponse(
            decision=decision,
            subscriber_id=request.subscriber_id,
            original_source_ip=original_source_ip,
            translated_source_ip=translation.public_ip if translation else None,
            translated_source_port=translation.public_port if translation else None,
            destination_ip=request.destination_ip,
            destination_port=request.destination_port,
            protocol=protocol,
            outgoing_interface=route.interface if route else None,
            next_hop=route.next_hop if route else None,
            matched_prefix=route.matched_prefix if route else None,
            trace=trace,
        )
