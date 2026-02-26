# backend/services.py
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta, timezone
from models import Task, Habit, HabitLog, User, WeeklyReport

# ════════════════════════════════════════
# TASK SERVICES
# ════════════════════════════════════════

# Replace get_tasks in services.py
def get_tasks(db: Session, user_id: int, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit

    base_query = db.query(Task).filter(
        Task.user_id == user_id,
        Task.is_deleted == False
    )

    total = base_query.count()

    tasks = (
        base_query
        .order_by(Task.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items":       tasks,
        "total":       total,
        "page":        page,
        "limit":       limit,
        "total_pages": max(1, -(-total // limit)),  # ceiling division
        "has_next":    page * limit < total,
        "has_prev":    page > 1,
    }




def create_task(db: Session, title: str, priority: str,
                description: str, due_date, user_id: int):
    task = Task(
        title=title,
        description=description,
        due_date=due_date,
        priority=priority,
        user_id=user_id
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def toggle_task(db: Session, task_id: int, user_id: int):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user_id,
        Task.is_deleted == False
    ).first()

    if not task:
        return None

    task.status = "completed" if task.status != "completed" else "pending"
    db.commit()
    db.refresh(task)
    return task


def edit_task(db: Session, task_id: int, user_id: int, new_title: str):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user_id,
        Task.is_deleted == False
    ).first()

    if not task:
        return None

    task.title = new_title
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int, user_id: int):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user_id,
        Task.is_deleted == False
    ).first()

    if not task:
        return False

    task.is_deleted = True   # soft delete — data is never truly lost
    db.commit()
    return True


# ════════════════════════════════════════
# HABIT SERVICES
# ════════════════════════════════════════

def _calculate_streak(logs: list, today: date) -> tuple[int, bool]:
    """
    Given a list of completed HabitLog objects (sorted newest first),
    returns (streak_count, is_logged_today).
    """
    streak = 0
    is_logged_today = False
    check_date = today

    for log in logs:
        if log.date == today:
            is_logged_today = True
            streak += 1
            check_date = today - timedelta(days=1)
        elif log.date == check_date:
            streak += 1
            check_date -= timedelta(days=1)
        elif log.date < check_date:
            break  # gap found — streak is broken

    return streak, is_logged_today


# Replace get_habits in services.py
def get_habits(db: Session, user_id: int, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    today  = date.today()

    base_query = db.query(Habit).filter(
        Habit.user_id == user_id,
        Habit.is_deleted == False
    )

    total  = base_query.count()
    habits = (
        base_query
        .order_by(Habit.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for habit in habits:
        logs = (
            db.query(HabitLog)
            .filter(HabitLog.habit_id == habit.id, HabitLog.completed == True)
            .order_by(HabitLog.date.desc())
            .all()
        )
        streak, is_logged_today = _calculate_streak(logs, today)
        result.append({
            "id":              habit.id,
            "name":            habit.name,
            "target_type":     habit.target_type,
            "user_id":         habit.user_id,
            "current_streak":  streak,
            "is_logged_today": is_logged_today,
        })

    return {
        "items":       result,
        "total":       total,
        "page":        page,
        "limit":       limit,
        "total_pages": max(1, -(-total // limit)),
        "has_next":    page * limit < total,
        "has_prev":    page > 1,
    }


def create_habit(db: Session, name: str, target_type: str, user_id: int):
    habit = Habit(name=name, target_type=target_type, user_id=user_id)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return {
        "id": habit.id, "name": habit.name,
        "target_type": habit.target_type, "user_id": habit.user_id,
        "current_streak": 0, "is_logged_today": False
    }


def edit_habit(db: Session, habit_id: int, user_id: int, new_name: str):
    habit = db.query(Habit).filter(
        Habit.id == habit_id,
        Habit.user_id == user_id,
        Habit.is_deleted == False
    ).first()

    if not habit:
        return None

    habit.name = new_name
    db.commit()
    db.refresh(habit)
    return {
        "id": habit.id, "name": habit.name,
        "target_type": habit.target_type, "user_id": habit.user_id,
        "current_streak": 0, "is_logged_today": False
    }


def delete_habit(db: Session, habit_id: int, user_id: int):
    habit = db.query(Habit).filter(
        Habit.id == habit_id,
        Habit.user_id == user_id,
        Habit.is_deleted == False
    ).first()

    if not habit:
        return False

    habit.is_deleted = True   # soft delete
    db.commit()
    return True


def log_habit(db: Session, habit_id: int, log_date: date,
              completed: bool, user_id: int):
    # Verify habit belongs to this user
    habit = db.query(Habit).filter(
        Habit.id == habit_id,
        Habit.user_id == user_id,
        Habit.is_deleted == False
    ).first()

    if not habit:
        return None

    # Upsert — update if exists, create if not
    existing = db.query(HabitLog).filter(
        HabitLog.habit_id == habit_id,
        HabitLog.date == log_date
    ).first()

    if existing:
        existing.completed = completed
        db.commit()
        db.refresh(existing)
        return existing

    new_log = HabitLog(habit_id=habit_id, date=log_date, completed=completed)
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log


# ════════════════════════════════════════
# DASHBOARD SERVICE
# ════════════════════════════════════════

def get_dashboard(db: Session, user_id: int):
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())

    # ── Tasks ──
    all_tasks       = db.query(Task).filter(Task.user_id == user_id, Task.is_deleted == False).all()
    total_tasks     = len(all_tasks)
    completed_tasks = sum(1 for t in all_tasks if t.status == "completed")
    pending_tasks   = total_tasks - completed_tasks
    task_rate       = round((completed_tasks / total_tasks * 100) if total_tasks else 0, 1)

    # ── Habits ──
    all_habits         = db.query(Habit).filter(Habit.user_id == user_id, Habit.is_deleted == False).all()
    total_habits       = len(all_habits)
    habits_logged_today = 0
    current_streaks    = []

    for habit in all_habits:
        logs = (
            db.query(HabitLog)
            .filter(HabitLog.habit_id == habit.id, HabitLog.completed == True)
            .order_by(HabitLog.date.desc())
            .all()
        )
        streak, is_logged_today = _calculate_streak(logs, today)
        if is_logged_today:
            habits_logged_today += 1

        current_streaks.append({
            "name":         habit.name,
            "streak":       streak,
            "logged_today": is_logged_today,
        })

    # ── Habit consistency this week ──
    total_possible = total_habits * 7 if total_habits else 0
    logs_this_week = (
        db.query(HabitLog)
        .join(Habit)
        .filter(
            Habit.user_id == user_id,
            Habit.is_deleted == False,
            HabitLog.completed == True,
            HabitLog.date >= week_start
        )
        .count()
    )
    habit_rate = round((logs_this_week / total_possible * 100) if total_possible else 0, 1)

    # ── Productivity score — 60% tasks, 40% habits ──
    productivity_score = round((task_rate * 0.6) + (habit_rate * 0.4))

    return {
        "total_tasks":            total_tasks,
        "completed_tasks":        completed_tasks,
        "pending_tasks":          pending_tasks,
        "task_completion_rate":   task_rate,
        "total_habits":           total_habits,
        "habits_logged_today":    habits_logged_today,
        "habit_consistency_rate": habit_rate,
        "productivity_score":     productivity_score,
        "current_streaks":        current_streaks,
    }


# ════════════════════════════════════════
# AUTH SERVICES
# ════════════════════════════════════════

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, name: str, email: str, password_hash: str):
    user = User(name=name, email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Add to services.py
import secrets
from models import RefreshToken

REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_refresh_token(db: Session, user_id: int) -> str:
    # Generate a secure random token
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    return token


def get_refresh_token(db: Session, token: str):
    return db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.revoked == False
    ).first()


def revoke_refresh_token(db: Session, token: str):
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).first()
    if db_token:
        db_token.revoked = True
        db.commit()


def revoke_all_user_tokens(db: Session, user_id: int):
    # Revoke all tokens for a user — useful for logout all devices
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()

def generate_weekly_report(db: Session, user: User) -> dict:
    """
    Calculates a full week summary for one user and saves it to DB.
    Called automatically by the background job every Monday.
    """
    today      = date.today()
    week_end   = today - timedelta(days=1)           # yesterday (Sunday)
    week_start = week_end - timedelta(days=6)         # last Monday

    # ── Tasks this week ──
    all_tasks = db.query(Task).filter(
        Task.user_id   == user.id,
        Task.is_deleted == False
    ).all()

    completed_this_week = sum(
        1 for t in all_tasks
        if t.status == 'completed'
    )
    total_tasks = len(all_tasks)

    # ── Habits this week ──
    all_habits = db.query(Habit).filter(
        Habit.user_id   == user.id,
        Habit.is_deleted == False
    ).all()

    logs_this_week = (
        db.query(HabitLog)
        .join(Habit)
        .filter(
            Habit.user_id    == user.id,
            Habit.is_deleted  == False,
            HabitLog.completed == True,
            HabitLog.date     >= week_start,
            HabitLog.date     <= week_end,
        )
        .count()
    )

    total_habits   = len(all_habits)
    possible_logs  = total_habits * 7
    habit_rate     = round((logs_this_week / possible_logs * 100) if possible_logs else 0)
    task_rate      = round((completed_this_week / total_tasks * 100) if total_tasks else 0)
    weekly_score   = round((task_rate * 0.6) + (habit_rate * 0.4))

    # ── Best streak this week ──
    best_habit     = None
    best_streak    = 0
    for habit in all_habits:
        logs = (
            db.query(HabitLog)
            .filter(HabitLog.habit_id == habit.id, HabitLog.completed == True)
            .order_by(HabitLog.date.desc())
            .all()
        )
        streak, _ = _calculate_streak(logs, today)
        if streak > best_streak:
            best_streak = streak
            best_habit  = habit.name

    # ── Build report text ──
    name = user.name or user.email.split('@')[0]

    if weekly_score >= 80:
        opening = f"Outstanding week, {name}! You were firing on all cylinders."
    elif weekly_score >= 60:
        opening = f"Solid week, {name}! You made real progress."
    elif weekly_score >= 40:
        opening = f"Decent effort this week, {name}. There's room to push harder."
    else:
        opening = f"Tough week, {name}. Every week is a fresh start — let's go."

    streak_line = (
        f"Your best streak is '{best_habit}' at {best_streak} days — keep it going!"
        if best_habit else "Start a habit this week to build your first streak."
    )

    report_text = (
        f"{opening}\n\n"
        f"Tasks: You completed {completed_this_week} out of {total_tasks} tasks ({task_rate}%).\n"
        f"Habits: You logged {logs_this_week} out of {possible_logs} possible check-ins ({habit_rate}%).\n"
        f"Weekly Score: {weekly_score}/100\n\n"
        f"{streak_line}\n\n"
        f"Week: {week_start.strftime('%b %d')} — {week_end.strftime('%b %d, %Y')}"
    )

    # ── Save to DB (avoid duplicates for same week) ──
    existing = db.query(WeeklyReport).filter(
        WeeklyReport.user_id    == user.id,
        WeeklyReport.week_start == week_start,
    ).first()

    if existing:
        existing.report = report_text
        existing.score  = weekly_score
        db.commit()
        return {"report": report_text, "score": weekly_score}

    new_report = WeeklyReport(
        user_id    = user.id,
        week_start = week_start,
        week_end   = week_end,
        report     = report_text,
        score      = weekly_score,
    )
    db.add(new_report)
    db.commit()
    return {"report": report_text, "score": weekly_score}


def get_latest_report(db: Session, user_id: int):
    return (
        db.query(WeeklyReport)
        .filter(WeeklyReport.user_id == user_id)
        .order_by(WeeklyReport.created_at.desc())
        .first()
    )


def get_all_users(db: Session):
    return db.query(User).all()