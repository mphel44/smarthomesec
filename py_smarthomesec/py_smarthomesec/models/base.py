"""
Base models and common mixins.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    """Mixin to add creation/update timestamps."""

    created_at: datetime | None = None
    updated_at: datetime | None = None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()


class SmartHomesecBaseModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        # Allow using Python attribute names (snake_case)
        # while accepting API names (often different)
        populate_by_name=True,
        # Validate data on assignment
        validate_assignment=True,
        # Ignore extra fields not defined in the model
        extra="ignore",
        # Use enum values for serialization
        use_enum_values=True,
    )
