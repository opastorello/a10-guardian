from pydantic import BaseModel, Field


class ZoneStatusResponse(BaseModel):
    zone_name: str = Field(..., json_schema_extra={"example": "203.0.113.50"})
    zone_id: str = Field(..., json_schema_extra={"example": "f6593c0b-9c93-4736-babc-8a3828e35af6"})
    operational_mode: str = Field(..., json_schema_extra={"example": "monitor"})
    services_count: int = Field(..., json_schema_extra={"example": 23})
    ip_list: list[str] = Field(default_factory=list, json_schema_extra={"example": ["203.0.113.50"]})


class ZoneListItem(BaseModel):
    zone_name: str = Field(..., json_schema_extra={"example": "203.0.113.50"})
    zone_id: str = Field(..., json_schema_extra={"example": "f6593c0b-9c93-4736-babc-8a3828e35af6"})
    operational_mode: str | None = Field(None, json_schema_extra={"example": "monitor"})


class ZoneListResponse(BaseModel):
    total: int = Field(..., json_schema_extra={"example": 24})
    page: int = Field(..., json_schema_extra={"example": 1})
    items: int = Field(..., json_schema_extra={"example": 40})
    zones: list[ZoneListItem] = Field(default_factory=list)


class UnderAttackResponse(BaseModel):
    under_attack: bool = Field(..., json_schema_extra={"example": True})
    monitored: bool = Field(..., json_schema_extra={"example": True})
    ip: str = Field(..., json_schema_extra={"example": "181.215.253.2"})
    block: str = Field(..., json_schema_extra={"example": "181.215.253.0-255"})


class ZoneIPCheckResponse(BaseModel):
    found: bool = Field(..., json_schema_extra={"example": True})


class ZoneIPMutationResponse(BaseModel):
    zone_name: str = Field(..., json_schema_extra={"example": "On-Demand"})
    ip: str = Field(..., json_schema_extra={"example": "203.0.113.5"})
    action: str = Field(..., json_schema_extra={"example": "added"})
    changed: bool = Field(..., json_schema_extra={"example": True})
    ip_count: int = Field(..., json_schema_extra={"example": 9})
