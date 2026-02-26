# backend/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional


# ════════════════════════════════════════
# AUTH / USER
# ════════════════════════════════════════
# Add to schemas.py
from typing import TypeVar, Generic

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items:       list[T]
    total:       int
    page:        int
    limit:       int
    total_pages: int
    has_next:    bool
    has_prev:    bool
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ════════════════════════════════════════
# TASKS
# ════════════════════════════════════════

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    due_date: Optional[datetime]
    priority: str
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True


# ════════════════════════════════════════
# HABITS
# ════════════════════════════════════════

class HabitCreate(BaseModel):
    name: str
    target_type: str = "daily"

class HabitResponse(BaseModel):
    id: int
    name: str
    target_type: str
    user_id: int
    current_streak: int = 0
    is_logged_today: bool = False

    class Config:
        from_attributes = True

class HabitLogCreate(BaseModel):
    date: date
    completed: bool = True

class HabitLogResponse(BaseModel):
    id: int
    habit_id: int
    date: date
    completed: bool

    class Config:
        from_attributes = True


# ════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════

class DashboardResponse(BaseModel):
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    task_completion_rate: float
    total_habits: int
    habits_logged_today: int
    habit_consistency_rate: float
    productivity_score: int
    current_streaks: list[dict]

# Add to schemas.py
class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# Add to schemas.py
class WeeklyReportResponse(BaseModel):
    id:         int
    user_id:    int
    week_start: date
    week_end:   date
    report:     str
    score:      int
    created_at: datetime

    class Config:
        from_attributes = True