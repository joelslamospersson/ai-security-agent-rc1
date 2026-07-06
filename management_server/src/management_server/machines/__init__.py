"""Machine registry and registration management."""

from management_server.machines.exceptions import (
    ApprovalError,
    DuplicateMachineError,
    InvalidTransitionError,
    MachineError,
    MachineNotFoundError,
    RegistrationError,
    RepositoryError,
    StateMachineError,
)
from management_server.machines.manager import MachineManager
from management_server.machines.metrics import RegistryMetricsCollector, RegistryMetricsSnapshot
from management_server.machines.registry import MachineRegistry
from management_server.machines.repository import MachineRepository
from management_server.machines.schemas import (
    ApprovalRequest,
    MachineInfo,
    MachineListResponse,
    RegistrationRequest,
    RegistrationResponse,
    RejectionRequest,
    RevocationRequest,
)
from management_server.machines.service import RegistrationService
from management_server.machines.state_machine import MachineState, MachineStateMachine

__all__ = [
    "ApprovalError",
    "ApprovalRequest",
    "DuplicateMachineError",
    "InvalidTransitionError",
    "MachineError",
    "MachineInfo",
    "MachineListResponse",
    "MachineManager",
    "MachineNotFoundError",
    "MachineRegistry",
    "MachineRepository",
    "MachineState",
    "MachineStateMachine",
    "RegistrationError",
    "RegistrationRequest",
    "RegistrationResponse",
    "RegistrationService",
    "RegistryMetricsCollector",
    "RegistryMetricsSnapshot",
    "RejectionRequest",
    "RepositoryError",
    "RevocationRequest",
    "RevocationRequest",
    "StateMachineError",
]
