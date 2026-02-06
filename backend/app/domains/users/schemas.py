from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)