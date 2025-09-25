import heapq
import math


class DownlinkScheduler:
    """Simple scheduler for downlink frames for class B/C nodes."""

    def __init__(self, link_delay: float = 0.0):
        self.queue: dict[int, list[tuple[float, int, int, object, object]]] = {}
        self._counter = 0
        # Track when each gateway becomes free to transmit
        self._gateway_busy: dict[int, float] = {}
        self.link_delay = link_delay

    @staticmethod
    def _payload_length(frame) -> int:
        """Return the byte length of ``frame`` payload."""
        if hasattr(frame, "payload"):
            try:
                return len(frame.payload)
            except Exception:
                pass
        if hasattr(frame, "to_bytes"):
            try:
                return len(frame.to_bytes())
            except Exception:
                pass
        return 0

    def schedule(self, node_id: int, time: float, frame, gateway, *, priority: int = 0):
        """Schedule a frame for a given node at ``time`` via ``gateway`` with optional ``priority``."""
        heapq.heappush(
            self.queue.setdefault(node_id, []),
            (time, priority, self._counter, frame, gateway),
        )
        self._counter += 1

    def schedule_class_b(
        self,
        node,
        after_time: float,
        frame,
        gateway,
        beacon_interval: float,
        ping_slot_interval: float,
        ping_slot_offset: float,
        *,
        last_beacon_time: float | None = None,
        priority: int = 0,
    ) -> float:
        """Schedule ``frame`` for ``node`` at its next ping slot."""
        duration = node.channel.airtime(node.sf, self._payload_length(frame))
        busy_until = self._gateway_busy.get(gateway.id, 0.0)
        search_start = max(after_time, busy_until - self.link_delay)
        slot_time = node.next_ping_slot_time(
            search_start,
            beacon_interval,
            ping_slot_interval,
            ping_slot_offset,
            last_beacon_time=last_beacon_time,
        )
        scheduled_times = [entry[0] for entry in self.queue.get(node.id, [])]
        max_attempts = 128
        attempts = 0
        while True:
            scheduled_at = slot_time + self.link_delay
            conflict = any(
                math.isclose(scheduled_at, existing, rel_tol=0.0, abs_tol=1e-6)
                for existing in scheduled_times
            )
            if not conflict and scheduled_at >= busy_until - 1e-9:
                break
            attempts += 1
            if attempts > max_attempts:
                raise RuntimeError("Unable to schedule Class B downlink: no ping slot available")
            search_start = slot_time + 1e-6
            slot_time = node.next_ping_slot_time(
                search_start,
                beacon_interval,
                ping_slot_interval,
                ping_slot_offset,
                last_beacon_time=last_beacon_time,
            )
        scheduled_at = slot_time + self.link_delay
        self.schedule(node.id, scheduled_at, frame, gateway, priority=priority)
        self._gateway_busy[gateway.id] = scheduled_at + duration
        return scheduled_at

    def schedule_class_c(self, node, time: float, frame, gateway, *, priority: int = 0):
        """Schedule a frame for a Class C node at ``time`` with optional ``priority`` and return the scheduled time."""
        duration = node.channel.airtime(node.sf, self._payload_length(frame))
        busy = self._gateway_busy.get(gateway.id, 0.0)
        if time < busy:
            time = busy
        time += self.link_delay
        self.schedule(node.id, time, frame, gateway, priority=priority)
        self._gateway_busy[gateway.id] = time + duration
        return time

    def schedule_class_a(
        self,
        node,
        after_time: float,
        rx1: float,
        rx2: float,
        frame,
        gateway,
        *,
        priority: int = 0,
    ) -> float:
        """Schedule ``frame`` for a Class A node in the next available window."""
        duration = node.channel.airtime(node.sf, self._payload_length(frame))
        busy = self._gateway_busy.get(gateway.id, 0.0)
        candidate = max(after_time, busy)
        if candidate <= rx1:
            t = rx1
        elif candidate <= rx2:
            t = rx2
        else:
            t = candidate
        t += self.link_delay
        self.schedule(node.id, t, frame, gateway, priority=priority)
        self._gateway_busy[gateway.id] = t + duration
        return t

    def schedule_beacon(self, after_time: float, frame, gateway, beacon_interval: float, *, priority: int = 0) -> float:
        """Schedule a beacon frame at the next beacon time after ``after_time``."""
        from .lorawan import next_beacon_time

        t = next_beacon_time(after_time, beacon_interval)
        t += self.link_delay
        self.schedule(0, t, frame, gateway, priority=priority)
        return t

    def pop_ready(self, node_id: int, current_time: float):
        """Return the next ready frame for ``node_id`` if any."""
        q = self.queue.get(node_id)
        if not q or q[0][0] > current_time:
            return None, None
        _, _, _, frame, gw = heapq.heappop(q)
        if not q:
            self.queue.pop(node_id, None)
        return frame, gw

    def next_time(self, node_id: int):
        q = self.queue.get(node_id)
        if not q:
            return None
        return q[0][0]
