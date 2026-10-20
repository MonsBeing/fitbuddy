import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DIR, get_settings
from app.database import get_db
from app.gemini_generator import generate_nutrition_tip_with_flash, generate_workout_gemini, update_workout_plan
from app.models import User, WorkoutPlan
from app.schemas import FeedbackRequest, UserInput

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
security = HTTPBasic()


def require_admin(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    settings = get_settings()
    expected_user = settings.admin_username
    expected_password = settings.admin_password
    user_ok = secrets.compare_digest(credentials.username.encode(), expected_user.encode())
    password_ok = bool(expected_password) and secrets.compare_digest(credentials.password.encode(), expected_password.encode())
    if not (user_ok and password_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin credentials are missing or invalid", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def _load_user(db: Session, user_id: str):
    user = db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User ID was not found. Create a plan first.")
    plan = db.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id).order_by(WorkoutPlan.id.desc()))
    if not plan:
        raise HTTPException(status_code=404, detail="No workout plan was found for this user.")
    return user, plan


def _user_input(user: User) -> UserInput:
    return UserInput(username=user.username, user_id=user.user_id, age=user.age, weight=user.weight, goal=user.goal, intensity=user.intensity, experience=user.experience)


def _result_context(request: Request, user: User, plan: WorkoutPlan, notice: str | None = None):
    active_plan = plan.updated_plan or plan.original_plan
    return {"request": request, "user": user, "workout_plan": json.loads(active_plan), "nutrition_tip": plan.nutrition_tip, "notice": notice, "model_used": plan.model_used}


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.post("/generate-workout", response_class=HTMLResponse, name="generate_workout")
def generate_workout(
    request: Request,
    username: Annotated[str, Form(min_length=2, max_length=80)],
    user_id: Annotated[str, Form(min_length=3, max_length=40)],
    age: Annotated[int, Form(ge=16, le=100)],
    weight: Annotated[float, Form(gt=25, le=350)],
    goal: Annotated[str, Form()],
    intensity: Annotated[str, Form()],
    experience: Annotated[str, Form()] = "beginner",
    db: Session = Depends(get_db),
):
    try:
        data = UserInput(username=username, user_id=user_id, age=age, weight=weight, goal=goal, intensity=intensity, experience=experience)
    except Exception as exc:
        return templates.TemplateResponse(request=request, name="index.html", context={"error": str(exc)}, status_code=422)
    user = db.scalar(select(User).where(User.user_id == data.user_id))
    if user is None:
        user = User(**data.model_dump())
        db.add(user)
        db.flush()
    else:
        for field, value in data.model_dump().items():
            setattr(user, field, value)
    plan_data, plan_model = generate_workout_gemini(data)
    tip, tip_model = generate_nutrition_tip_with_flash(data)
    plan = WorkoutPlan(user=user, original_plan=json.dumps(plan_data), nutrition_tip=tip, model_used=f"plan: {plan_model}; tip: {tip_model}")
    db.add(plan)
    db.commit()
    db.refresh(user)
    db.refresh(plan)
    notice = "Plan ready. Add a Gemini API key in .env to enable live AI generation." if "fallback" in plan.model_used else None
    return templates.TemplateResponse(request=request, name="result.html", context=_result_context(request, user, plan, notice))


@router.post("/submit-feedback", response_class=HTMLResponse, name="submit_feedback")
def submit_feedback(request: Request, user_id: Annotated[str, Form()], feedback: Annotated[str, Form(min_length=5, max_length=1000)], db: Session = Depends(get_db)):
    try:
        data = FeedbackRequest(user_id=user_id, feedback=feedback)
        user, plan = _load_user(db, data.user_id)
        current = json.loads(plan.updated_plan or plan.original_plan)
        updated, model = update_workout_plan(current, _user_input(user), data.feedback)
        plan.updated_plan = json.dumps(updated)
        plan.revision_feedback = data.feedback
        plan.model_used = f"plan update: {model}"
        db.commit()
        notice = "Your feedback was saved and the plan was updated." + (" Add a Gemini API key to enable live AI revisions." if "fallback" in model else "")
        return templates.TemplateResponse(request=request, name="result.html", context=_result_context(request, user, plan, notice))
    except HTTPException as exc:
        return templates.TemplateResponse(request=request, name="index.html", context={"error": exc.detail}, status_code=exc.status_code)
    except Exception:
        return templates.TemplateResponse(request=request, name="index.html", context={"error": "Please check the user ID and feedback and try again."}, status_code=422)


@router.get("/view-all-users", response_class=HTMLResponse, name="all_users")
def all_users(request: Request, _: str = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    records = []
    for user in users:
        plans = db.scalars(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id).order_by(WorkoutPlan.id.desc())).all()
        records.append({"user": user, "plans": plans})
    return templates.TemplateResponse(request=request, name="all_users.html", context={"records": records})


@router.post("/admin/users/{user_id}/delete", name="delete_user")
def delete_user(user_id: int, _: str = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/view-all-users", status_code=303)


@router.post("/api/plans", status_code=201)
def create_plan_api(data: UserInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.user_id == data.user_id))
    if user is None:
        user = User(**data.model_dump())
        db.add(user)
        db.flush()
    else:
        for field, value in data.model_dump().items():
            setattr(user, field, value)
    plan, plan_model = generate_workout_gemini(data)
    tip, tip_model = generate_nutrition_tip_with_flash(data)
    record = WorkoutPlan(user=user, original_plan=json.dumps(plan), nutrition_tip=tip, model_used=f"plan: {plan_model}; tip: {tip_model}")
    db.add(record)
    db.commit()
    return {"user_id": user.user_id, "plan_id": record.id, "workout_plan": plan, "nutrition_tip": tip, "model_used": record.model_used}


@router.post("/api/plans/{user_id}/feedback")
def update_plan_api(user_id: str, data: FeedbackRequest, db: Session = Depends(get_db)):
    if data.user_id != user_id:
        raise HTTPException(status_code=422, detail="Path user_id must match the body user_id")
    user, plan = _load_user(db, user_id)
    revised, model = update_workout_plan(json.loads(plan.updated_plan or plan.original_plan), _user_input(user), data.feedback)
    plan.updated_plan = json.dumps(revised)
    plan.revision_feedback = data.feedback
    plan.model_used = model
    db.commit()
    return {"user_id": user.user_id, "workout_plan": revised, "nutrition_tip": plan.nutrition_tip, "model_used": model}


@router.get("/api/users", dependencies=[Depends(require_admin)])
def list_users_api(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [{"user_id": u.user_id, "username": u.username, "age": u.age, "weight": u.weight, "goal": u.goal, "intensity": u.intensity, "experience": u.experience, "plans": [{"original_plan": json.loads(p.original_plan), "updated_plan": json.loads(p.updated_plan) if p.updated_plan else None, "feedback": p.revision_feedback} for p in u.plans]} for u in users]
