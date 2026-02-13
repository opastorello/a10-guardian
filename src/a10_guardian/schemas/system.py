from pydantic import BaseModel, ConfigDict, Field


class SystemInfoResponse(BaseModel):
    hostname: str = Field(..., json_schema_extra={"example": "aGalaxy-Node-01"})
    uptime: str = Field(..., json_schema_extra={"example": "19 days, 17:23:55"})
    product_name: str | None = Field(None, json_schema_extra={"example": "VMware"})
    agalaxy_version: str | None = Field(None, json_schema_extra={"example": "5.0.13.29"})
    serial_number: str | None = Field(None, json_schema_extra={"example": "TH1234567890"})


class LicenseInfo(BaseModel):
    license_type: str | None = Field(None, description="License type")
    max_devices: int | None = Field(None, description="Maximum devices allowed")
    max_objects: int | None = Field(None, description="Maximum objects allowed")
    remaining: str | None = Field(None, description="Usage (e.g. '2 out of 2')")
    expires_at: str | None = Field(None, description="Expiration date")


class DeviceInfo(BaseModel):
    dns_name: str | None = Field(None, json_schema_extra={"example": "TPS-BOX1"})
    mgmt_ip_address: str | None = Field(None, json_schema_extra={"example": "10.128.1.191"})
    model: str | None = Field(None, json_schema_extra={"example": "TH6435 TPS"})
    firmware_version: str | None = Field(None, json_schema_extra={"example": "5.16"})
    serial_number: str | None = Field(None, json_schema_extra={"example": "TH64123014170004"})
    admin_status_label: str | None = Field(None, json_schema_extra={"example": "ENABLED"})
    oper_status_label: str | None = Field(None, json_schema_extra={"example": "CONNECTED"})
    id: str | None = Field(None, json_schema_extra={"example": "2f53c8ba-0062-4aae-8924-9b8174af6d5f"})

    model_config = ConfigDict(extra="allow")


class DeviceListResponse(BaseModel):
    total: int = Field(..., json_schema_extra={"example": 2})
    items: int | None = Field(None, json_schema_extra={"example": 20})
    page: int = Field(..., json_schema_extra={"example": 1})
    object_list: list[DeviceInfo] = Field(default_factory=list, description="List of devices")

    model_config = ConfigDict(extra="allow")
