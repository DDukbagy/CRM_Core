from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


class InstructorStaffCreate(BaseModel):
    staff_email: EmailStr


class InstructorStaffRead(BaseModel):
    staff_user_id: UUID
    email: EmailStr | None
    username: str
    display_name: str
    created_at: datetime
