from __future__ import annotations

import os
import socket  # audit: allow
from dataclasses import dataclass, field


OFFLINE_ENV_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")


@dataclass(frozen=True)
class OfflineStatus:
    env_ok: bool
    network_blocked: bool
    missing_env: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.env_ok and self.network_blocked


def check_offline_status(probe_network: bool = False, timeout: float = 1.0) -> OfflineStatus:
    missing = [name for name in OFFLINE_ENV_VARS if os.environ.get(name) != "1"]
    network_blocked = True

    if probe_network:
        try:
            with socket.create_connection(("1.1.1.1", 53), timeout=timeout):  # audit: allow
                network_blocked = False
        except OSError:
            network_blocked = True

    return OfflineStatus(env_ok=not missing, network_blocked=network_blocked, missing_env=missing)
