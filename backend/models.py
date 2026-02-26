# backend/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Date, ForeignKey, Index
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    email         = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="user")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tasks  = relationship("Task",  back_populates="owner", cascade="all, delete-orphan")
    habits = relationship("Habit", back_populates="owner", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status      = Column(String, default="pending")   # pending | completed
    due_date    = Column(DateTime, nullable=True)
    priority    = Column(String, default="medium")    # high | medium | low
    is_deleted  = Column(Boolean, default=False)      # soft delete
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="tasks")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tasks_user_id",        "user_id"),
        Index("ix_tasks_user_status",    "user_id", "status"),
        Index("ix_tasks_user_deleted",   "user_id", "is_deleted"),
    )


class Habit(Base):
    __tablename__ = "habits"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    target_type = Column(String, default="daily")
    is_deleted  = Column(Boolean, default=False)      # soft delete
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="habits")
    logs  = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_habits_user_id",      "user_id"),
        Index("ix_habits_user_deleted", "user_id", "is_deleted"),
    )


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id        = Column(Integer, primary_key=True, index=True)
    habit_id  = Column(Integer, ForeignKey("habits.id"), nullable=False)
    date      = Column(Date, nullable=False)
    completed = Column(Boolean, default=False)

    habit = relationship("Habit", back_populates="logs")

    # Most queried combination — habit + date
    __table_args__ = (
        Index("ix_habit_logs_habit_date", "habit_id", "date"),
    )

# Add to models.py
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    token      = Column(String, unique=True, index=True, nullable=False)  # unique already creates index
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        # ← removed ix_refresh_tokens_token from here, unique=True above handles it
    )

# Add to models.py
class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end   = Column(Date, nullable=False)
    report     = Column(String, nullable=False)   # the generated text
    score      = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_weekly_reports_user_id", "user_id"),
    )