import json
import re
from typing import Any

from app.config import get_settings
from app.schemas import UserInput

GOAL_LABELS = {
    "weight_loss": "weight loss", "muscle_gain": "muscle gain",
    "general_fitness": "general fitness", "flexibility": "flexibility",
    "endurance": "endurance",
}


def _fallback_plan(user: UserInput) -> dict[str, Any]:
    goal = GOAL_LABELS[user.goal]
    if user.goal == "weight_loss":
        focuses = ["Full body strength", "Low-impact cardio", "Upper body + core", "Active recovery", "Lower body strength", "Steady cardio", "Rest and mobility"]
    elif user.goal == "muscle_gain":
        focuses = ["Upper body push", "Lower body", "Upper body pull", "Recovery and mobility", "Full body strength", "Glutes and core", "Rest"]
    elif user.goal == "flexibility":
        focuses = ["Full-body mobility", "Yoga flow", "Hips and hamstrings", "Gentle recovery", "Shoulders and spine", "Balance and mobility", "Rest"]
    elif user.goal == "endurance":
        focuses = ["Easy aerobic session", "Strength and core", "Intervals", "Active recovery", "Tempo cardio", "Long easy session", "Rest"]
    else:
        focuses = ["Full body strength", "Easy cardio", "Core and balance", "Active recovery", "Full body strength", "Cardio and mobility", "Rest"]
    days = []
    for idx, focus in enumerate(focuses):
        rest_day = "Rest" in focus
        recovery = "recovery" in focus.lower() or "mobility" in focus.lower() or "yoga" in focus.lower()
        if rest_day:
            exercises = [{"name": "Easy walk or complete rest", "sets_reps": "Optional 15-20 min", "rest": "As needed"}]
        elif recovery:
            exercises = [
                {"name": "Gentle mobility flow", "sets_reps": "2 rounds, 30 sec each", "rest": "30 sec"},
                {"name": "Easy walk", "sets_reps": "10-20 min", "rest": "Comfortable pace"},
            ]
        else:
            reps = "2-3 sets of 8-12 reps" if user.intensity != "high" else "3 sets of 8-12 reps"
            exercises = [
                {"name": "Bodyweight squat", "sets_reps": reps, "rest": "60-90 sec"},
                {"name": "Incline push-up", "sets_reps": reps, "rest": "60-90 sec"},
                {"name": "Hip hinge", "sets_reps": reps, "rest": "60-90 sec"},
                {"name": "Brisk walk", "sets_reps": "10-20 min", "rest": "Easy pace"},
            ]
        days.append({"day": f"Day {idx + 1}", "focus": focus, "warmup": "5-8 min easy movement and dynamic stretches", "exercises": exercises, "cooldown": "5 min easy movement and comfortable stretching."})
    return {"title": f"7-day plan for {goal}", "days": days, "source": "local fallback"}


def _generate_text(model: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    settings = get_settings()
    client = genai.Client(api_key=settings.google_api_key, http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)))
    response = client.models.generate_content(model=model, contents=prompt)
    text = response.text
    if not text:
        raise ValueError("Gemini returned an empty response")
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The AI response was not valid JSON")
        value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict) or not isinstance(value.get("days"), list) or len(value["days"]) != 7:
        raise ValueError("The AI response must include exactly seven workout days")
    for index, day in enumerate(value["days"], 1):
        if not isinstance(day, dict):
            raise ValueError("Invalid workout day in AI response")
        day.setdefault("day", f"Day {index}")
        day.setdefault("focus", "General fitness")
        day.setdefault("warmup", "5-10 min gentle warm-up")
        day.setdefault("exercises", [])
        day.setdefault("cooldown", "5 min gentle cooldown")
        day["exercises"] = [x for x in day["exercises"] if isinstance(x, dict)]
    value.setdefault("title", "Your 7-day workout plan")
    value["source"] = "Gemini"
    return value


def generate_workout_gemini(user: UserInput) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    if not settings.google_api_key:
        return _fallback_plan(user), "local fallback"
    prompt = f"""Create a safe, practical 7-day fitness plan for this adult. Use reasonable volume, include at least one rest or active recovery day, and avoid diagnosing or making medical claims. If information is missing, use conservative bodyweight options. Return ONLY valid JSON with this exact structure: {{"title":"...","days":[{{"day":"Day 1","focus":"...","warmup":"...","exercises":[{{"name":"...","sets_reps":"...","rest":"..."}}],"cooldown":"..."}}]}}. Include exactly 7 day objects and 2-5 exercises on training days. User: age {user.age}, weight {user.weight} kg, goal {GOAL_LABELS[user.goal]}, preferred intensity {user.intensity}, experience {user.experience}."""
    try:
        return _extract_json(_generate_text(settings.plan_model, prompt)), settings.plan_model
    except Exception:
        # Keep the app usable during provider outages; do not expose provider details to visitors.
        return _fallback_plan(user), "local fallback (Gemini unavailable)"


def generate_nutrition_tip_with_flash(user: UserInput) -> tuple[str, str]:
    settings = get_settings()
    if not settings.google_api_key:
        return _fallback_tip(user), "local fallback"
    prompt = f"Give one concise, general nutrition or recovery tip (maximum 60 words) for an adult pursuing {GOAL_LABELS[user.goal]}. Avoid prescriptive calorie targets, supplements, medical claims, and guarantees."
    try:
        return _generate_text(settings.tip_model, prompt), settings.tip_model
    except Exception:
        return _fallback_tip(user), "local fallback (Gemini unavailable)"


def _fallback_tip(user: UserInput) -> str:
    tips = {
        "weight_loss": "Build meals around vegetables, a satisfying protein source, and fiber-rich foods. Avoid extreme restriction; steady habits are easier to sustain.",
        "muscle_gain": "Include a protein-rich food in regular meals and have a balanced snack after training if hungry. Consistent meals and sleep support recovery.",
        "general_fitness": "Drink to thirst throughout the day and aim for varied meals with vegetables, whole grains, and protein.",
        "flexibility": "Stay hydrated and include varied, nourishing meals; gentle movement and adequate sleep also support recovery.",
        "endurance": "For longer sessions, have a familiar carbohydrate-rich snack beforehand and replace fluids afterward.",
    }
    return tips[user.goal]


def update_workout_plan(original: dict[str, Any], user: UserInput, feedback: str) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    if not settings.google_api_key:
        revised = dict(original)
        revised["title"] = "Updated plan (AI key not configured)"
        revised["feedback_note"] = f"Your request was saved: {feedback.strip()}"
        revised["source"] = "local fallback"
        request = feedback.lower()
        if any(word in request for word in ("cardio", "running", "run", "aerobic", "endurance")):
            for day in revised["days"]:
                if "rest" not in day.get("focus", "").lower():
                    day["focus"] = "Cardio focus - " + day.get("focus", "training")
                    day["exercises"] = [{"name": "Brisk walk or comfortable cardio", "sets_reps": "15-25 min at conversational pace", "rest": "Slow down or stop if uncomfortable"}]
                    break
        elif any(word in request for word in ("rest", "recovery", "easier", "gentler", "low impact")):
            for day in revised["days"]:
                if "rest" not in day.get("focus", "").lower() and "recovery" not in day.get("focus", "").lower():
                    day["focus"] = "Active recovery"
                    day["exercises"] = [{"name": "Easy walk or gentle mobility", "sets_reps": "10-20 min, optional", "rest": "As needed"}]
                    break
        elif any(word in request for word in ("yoga", "stretch", "mobility", "flexibility")):
            for day in revised["days"]:
                if "rest" not in day.get("focus", "").lower():
                    day["focus"] = "Yoga and mobility"
                    day["exercises"] = [{"name": "Gentle yoga or mobility flow", "sets_reps": "15-25 min, comfortable range", "rest": "Pause as needed"}]
                    break
        return revised, "local fallback"
    prompt = f"Revise this seven-day workout JSON according to the user's feedback. Preserve exactly seven days, safe progressive volume, warm-up, exercises, cooldown, and a rest/recovery day. Return only valid JSON with title and days using the same fields. Treat feedback as a preference, not medical advice; ignore requests that could lead to unsafe training and use a safer alternative. User profile: age {user.age}, goal {GOAL_LABELS[user.goal]}, intensity {user.intensity}, experience {user.experience}. Feedback: {feedback}\nCurrent plan JSON: {json.dumps(original, ensure_ascii=False)}"
    try:
        return _extract_json(_generate_text(settings.plan_model, prompt)), settings.plan_model
    except Exception:
        revised = dict(original)
        revised["title"] = "Updated plan (local fallback)"
        revised["feedback_note"] = f"Feedback saved: {feedback.strip()}"
        return revised, "local fallback (Gemini unavailable)"
