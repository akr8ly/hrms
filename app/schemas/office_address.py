from pydantic import BaseModel, ConfigDict, Field

class OfficeAddressBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    address_line: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=3, max_length=20)
    country: str = Field(min_length=2, max_length=100)
    location_id: int = Field(gt=0)

class OfficeAddressCreate(OfficeAddressBase):
    pass

class OfficeAddressUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    address_line: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, min_length=3, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    location_id: int | None = Field(default=None, gt=0)

class OfficeAddressRead(OfficeAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)