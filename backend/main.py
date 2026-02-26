# backend/main.py
import logging
import time
from datetime import datetime, timedelta, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
# Update this import line if your project structure is different
import models
import schemas
import services
from models import Base
from apscheduler.schedulers.background import BackgroundScheduler
# Rate limiter — identifies users by their IP address
limiter = Limiter(key_func=get_remote_address)
# ════════════════════════════════════════
# CONFIG  (reads from .env automatically)
# ════════════════════════════════════════

class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str = "sqlite:///./lifeos.db"
    DEBUG: bool = False
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   # 7 days

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()


# ════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("lifeos.log", encoding="utf-8"),
    ],
)
logging.getLogger("passlib").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("lifeos")


# ════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine       = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine, checkfirst=True)  # remove this once Alembic is set up

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ════════════════════════════════════════
# SECURITY  (password hashing + JWT)
# ════════════════════════════════════════

# ════════════════════════════════════════
# SECURITY  (password hashing + JWT)
# ════════════════════════════════════════

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

def hash_password(password: str) -> str:
    # Bcrypt requires bytes. We also truncate to 72 bytes to prevent length errors.
    pwd_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    # Encode both strings to bytes for comparison
    plain_bytes = plain[:72].encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    try:
        # Check if the plain password matches the hashed one
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except (ValueError, TypeError, Exception):
        # Triggers if the hashed string is invalid, corrupted, or missing
        return False

def create_access_token(email: str) -> str:
    expire  = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = services.get_user_by_email(db, email)
    if not user:
        raise credentials_exception
    return user


# ════════════════════════════════════════
# APP + MIDDLEWARE
# ════════════════════════════════════════

app = FastAPI(
    title="LifeOS API",
    version="3.0.0",
    description="Personal productivity system — tasks, habits, dashboard",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",
        "https://lifeos-2-cob5djzec-ananta12-ds-projects.vercel.app",
        "https://lifeos-ananta.vercel.app",  # add your clean domain here too
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    ms       = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms:.0f}ms)")
    return response


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# ════════════════════════════════════════
# BACKGROUND JOB — runs every Monday 8am
# ════════════════════════════════════════

def run_weekly_reports():
    """
    Automatically called every Monday at 8am.
    Generates a report for every user in the database.
    """
    logger.info("Background job started — generating weekly reports...")
    db = SessionLocal()
    try:
        users = services.get_all_users(db)
        for user in users:
            try:
                result = services.generate_weekly_report(db, user)
                logger.info(f"Report generated for {user.email} — score: {result['score']}")
            except Exception as e:
                logger.error(f"Failed to generate report for {user.email}: {e}")
        logger.info(f"Weekly reports done — processed {len(users)} users.")
    finally:
        db.close()


# Start scheduler — won't block the server
scheduler = BackgroundScheduler()
scheduler.add_job(
    run_weekly_reports,
    trigger='cron',
    day_of_week='mon',    # every Monday
    hour=8,               # at 8am
    minute=0,
    id='weekly_reports',
    replace_existing=True,
)
scheduler.start()
logger.info("Background scheduler started — weekly reports run every Monday at 8am")
# ════════════════════════════════════════
# ROUTES — all under /api/v1/
# ════════════════════════════════════════

# ── Health Check ────────────────────────
@app.get("/")
def health_check():
    return {"status": "online", "version": "3.0.0", "message": "LifeOS API is running"}


# ── Auth ────────────────────────────────
@app.post("/api/v1/users/", response_model=schemas.UserResponse, tags=["Auth"])
@limiter.limit("3/minute")   # ← add this line
def register(
    request: Request,        # ← add request as first parameter
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    if services.get_user_by_email(db, user.email):
        logger.warning(f"Registration attempt with existing email: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = services.create_user(db, user.name, user.email, hash_password(user.password))
    logger.info(f"New user registered: {user.email}")
    return new_user

# ── Weekly Reports ───────────────────────
@app.get("/api/v1/reports/latest", response_model=schemas.WeeklyReportResponse, tags=["Reports"])
def get_latest_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    report = services.get_latest_report(db, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="No report yet — check back after Monday!")
    return report


@app.post("/api/v1/reports/generate", tags=["Reports"])
def generate_report_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Manually trigger report generation for the current user.
    Useful for testing without waiting until Monday.
    """
    result = services.generate_weekly_report(db, current_user)
    logger.info(f"Manual report generated for {current_user.email}")
    return {"message": "Report generated!", "score": result["score"]}

@app.post("/api/v1/login", response_model=schemas.TokenPair, tags=["Auth"])
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = services.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning(f"Failed login attempt: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token  = create_access_token(user.email)
    refresh_token = services.create_refresh_token(db, user.id)

    logger.info(f"User logged in: {user.email}")
    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer"
    }
@app.post("/api/v1/refresh", response_model=schemas.TokenPair, tags=["Auth"])
def refresh_token(
    payload: schemas.RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    # Look up the refresh token in DB
    db_token = services.get_refresh_token(db, payload.refresh_token)

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Check it hasn't expired
    if datetime.now(timezone.utc) > db_token.expires_at.replace(tzinfo=timezone.utc):
        services.revoke_refresh_token(db, payload.refresh_token)
        raise HTTPException(status_code=401, detail="Refresh token expired. Please log in again.")

    # Get the user
    user = db.query(models.User).filter(models.User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate tokens — revoke old, issue new pair
    services.revoke_refresh_token(db, payload.refresh_token)
    new_access_token  = create_access_token(user.email)
    new_refresh_token = services.create_refresh_token(db, user.id)

    logger.info(f"Tokens rotated for: {user.email}")
    return {
        "access_token":  new_access_token,
        "refresh_token": new_refresh_token,
        "token_type":    "bearer"
    }


@app.post("/api/v1/logout", tags=["Auth"])
def logout(
    payload: schemas.RefreshTokenRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    services.revoke_refresh_token(db, payload.refresh_token)
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}

@app.post("/api/v1/users/change-password", tags=["Auth"])
def change_password(
    payload: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    logger.info(f"Password changed for: {current_user.email}")
    return {"message": "Password updated successfully"}


# ── Tasks ────────────────────────────────
# Replace get_tasks route in main.py
@app.get("/api/v1/tasks/", tags=["Tasks"])
def get_tasks(
    page:  int = 1,
    limit: int = 20,
    db:    Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    data = services.get_tasks(db, current_user.id, page, limit)
    logger.info(f"{current_user.email} — fetched tasks page {page}")
    return data


@app.post("/api/v1/tasks/", response_model=schemas.TaskResponse, tags=["Tasks"])
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_task = services.create_task(
        db, task.title, task.priority,
        task.description, task.due_date, current_user.id
    )
    logger.info(f"{current_user.email} — created task: '{task.title}'")
    return new_task


@app.put("/api/v1/tasks/{task_id}/complete", response_model=schemas.TaskResponse, tags=["Tasks"])
def toggle_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    task = services.toggle_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(f"{current_user.email} — toggled task {task_id} → {task.status}")
    return task


@app.put("/api/v1/tasks/{task_id}", response_model=schemas.TaskResponse, tags=["Tasks"])
def edit_task(
    task_id: int,
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    task = services.edit_task(db, task_id, current_user.id, payload.title)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(f"{current_user.email} — edited task {task_id}")
    return task


@app.delete("/api/v1/tasks/{task_id}", tags=["Tasks"])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not services.delete_task(db, task_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(f"{current_user.email} — deleted task {task_id}")
    return {"message": "Task deleted"}


# ── Habits ───────────────────────────────
# Replace get_habits route in main.py
@app.get("/api/v1/habits/", tags=["Habits"])
def get_habits(
    page:  int = 1,
    limit: int = 20,
    db:    Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    data = services.get_habits(db, current_user.id, page, limit)
    logger.info(f"{current_user.email} — fetched habits page {page}")
    return data


@app.post("/api/v1/habits/", response_model=schemas.HabitResponse, tags=["Habits"])
def create_habit(
    habit: schemas.HabitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_habit = services.create_habit(db, habit.name, habit.target_type, current_user.id)
    logger.info(f"{current_user.email} — created habit: '{habit.name}'")
    return new_habit


@app.put("/api/v1/habits/{habit_id}", response_model=schemas.HabitResponse, tags=["Habits"])
def edit_habit(
    habit_id: int,
    payload: schemas.HabitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    habit = services.edit_habit(db, habit_id, current_user.id, payload.name)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    logger.info(f"{current_user.email} — edited habit {habit_id}")
    return habit


@app.delete("/api/v1/habits/{habit_id}", tags=["Habits"])
def delete_habit(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not services.delete_habit(db, habit_id, current_user.id):
        raise HTTPException(status_code=404, detail="Habit not found")
    logger.info(f"{current_user.email} — deleted habit {habit_id}")
    return {"message": "Habit deleted"}


@app.post("/api/v1/habits/{habit_id}/logs/", response_model=schemas.HabitLogResponse, tags=["Habits"])
def log_habit(
    habit_id: int,
    log: schemas.HabitLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = services.log_habit(db, habit_id, log.date, log.completed, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Habit not found")
    logger.info(f"{current_user.email} — logged habit {habit_id} on {log.date}")
    return result


# ── Dashboard ────────────────────────────
@app.get("/api/v1/dashboard/", response_model=schemas.DashboardResponse, tags=["Dashboard"])
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    data = services.get_dashboard(db, current_user.id)
    logger.info(f"{current_user.email} — fetched dashboard")
    return data