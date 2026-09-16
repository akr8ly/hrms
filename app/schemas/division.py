from pydantic import BaseModel, ConfigDict, Field, model_validator

class DivisionBase(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class DivisionCreate(DivisionBase):

    pass


class DivisionUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
  
        for field in ("code", "name"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DivisionRead(DivisionBase):

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
