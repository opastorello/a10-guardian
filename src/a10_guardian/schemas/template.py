"""Pydantic schemas for zone template management."""

from pydantic import BaseModel, Field


class ZoneServiceConfig(BaseModel):
    """Configuration for a single zone service (protocol + port + profile)."""

    profile_name: str | None = None
    protocol: str
    port: int | str | None = None


class ZonePortConfig(BaseModel):
    """Port configuration containing list of zone services."""

    zone_service_list: list[ZoneServiceConfig]


class ZonePayload(BaseModel):
    """Validates the zone creation payload structure."""

    advertised_enable: bool = False
    telemetry_enable: bool = False
    log_enable: bool = False
    log_periodic: bool = False
    zone_oper_policy: str | None = None
    packet_capture_policy: str = "A10_Default"
    operational_mode: str = "idle"
    is_per_addr_glid_set: bool = False
    profile_name: str | None = None
    port: ZonePortConfig
    src_port: list = []
    continuous_learning: bool = False
    detection: dict = Field(default_factory=lambda: {"service_discovery": {"pkt_rate_threshold": None}})
    zone_learning_jobs: list = []
    device_group: str | None = None


class IndicatorConfig(BaseModel):
    """Detection indicator configuration (pkt-rate, syn-rate, etc)."""

    name: str
    value: int = 0
    score: int = 0


class ProtectionValueConfig(BaseModel):
    """Protection configuration per protocol/port."""

    protocol: str
    port: int | str | None = None
    port_range_start: int | None = None
    port_range_end: int | None = None
    port_other: str | None = None
    zone_escalation_score: int | None = None
    indicators: list[IndicatorConfig]


class MonitorPayload(BaseModel):
    """Validates the monitor/deploy payload structure."""

    algorithm: str = "max"
    sensitivity: str = "medium"
    manual_thresholds: bool = False
    deployZone: bool = True
    protection_values: list[ProtectionValueConfig]


class ZoneTemplate(BaseModel):
    """Complete template with both zone and monitor payloads."""

    name: str
    zone_payload: ZonePayload
    monitor_payload: MonitorPayload


class TemplateResponse(BaseModel):
    """Response model for template retrieval."""

    name: str
    template: ZoneTemplate
    created_at: str | None = None
    modified_at: str | None = None
    file_size_kb: float


class TemplateListItem(BaseModel):
    """Summary item for template list endpoint."""

    name: str
    services_count: int
    protection_values_count: int
    profile_name: str | None = None
    device_group: str | None = None
    file_path: str


class TemplateValidationResult(BaseModel):
    """Result of template validation (structure + A10)."""

    valid: bool
    errors: list[str] = []
    a10_validation: dict = Field(default_factory=dict, description="Results from A10 validation checks")
