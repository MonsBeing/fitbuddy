# FitBuddy

FitBuddy is a complete FastAPI application for creating personalized seven-day workout plans, offering general nutrition and recovery tips, and updating plans from user feedback. It includes a responsive Jinja2 web interface, JSON API, SQLite persistence, and a password-protected coach dashboard.

The project PDF describes Gemini 1.5 Pro and the older `google-generativeai` package. Those identifiers and that SDK have since been superseded. FitBuddy uses Google's current `google-genai` SDK and configurable model IDs (default `gemini-3.8-flash`). Check model availability for your account in [Google AI Studio](https://aistudio.google.com/) and update the two model settings in `.env` if needed. Without a key, the app runs with a local deterministic plan and tip generator; feedback still revises the plan for common requests such as more cardio, extra recovery, or yoga.

## Features

- Profile form for a name, unique user ID, age, weight, fitness goal, training experience, and preferred intensity.
- Seven-day plans with warmups, exercises, sets/reps, rest guidance, and cooldowns.
- Goal-oriented general nutrition or recovery tip.
- Feedback-based plan revisions while preserving the original version.
- Persistent SQLite storage. Reusing a user ID updates that profile and creates another plan history entry.
- JSON endpoints for plan creation and feedback, plus OpenAPI docs at `/docs`.
- Coach dashboard at `/view-all-users`, protected with HTTP Basic authentication, with plan history and user deletion.
- Local fallback behavior when no Gemini API key is configured or the provider is unavailable.

## Requirements

- Python 3.10 or newer (Python 3.11+ recommended).
- Visual Studio Code and its Python extension.
- A Gemini API key is optional; the app works without it in local fallback mode.

## Setup in VS Code on Windows

1. Open this project folder in VS Code and open **Terminal → New Terminal**.
2. Create and activate a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again. Alternatively, use the VS Code Command Palette → **Python: Select Interpreter** and choose `.venv`.

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Create your local configuration:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env`. For live Gemini responses, paste your key into `GOOGLE_API_KEY`. Set a unique `ADMIN_PASSWORD` for the coach dashboard. Keep `.env` private; it is excluded from Git. With `GOOGLE_API_KEY` blank, the local fallback is used.

5. In VS Code, select the `.venv` Python interpreter if prompted.

## Run

From the project root with the virtual environment activated:

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> for the app. API documentation is at <http://127.0.0.1:8000/docs>, a simple status check is at <http://127.0.0.1:8000/health>, and the coach dashboard is at <http://127.0.0.1:8000/view-all-users>. The browser asks for the `ADMIN_USERNAME` and `ADMIN_PASSWORD` configured in `.env`.

Stop the server with **Ctrl+C** in the VS Code terminal.

## Public HTTPS deployment on Render

`render.yaml` defines a public Python web service, a managed Postgres database, an automatically generated dashboard password, and `/health` as the health check. Render provides the `onrender.com` URL and TLS certificate after the service deploys.

The current public deployment is [https://fitbuddy-xrud.onrender.com](https://fitbuddy-xrud.onrender.com). The home page and `/health` endpoint have been verified over HTTPS. The `/docs` API explorer is available at [https://fitbuddy-xrud.onrender.com/docs](https://fitbuddy-xrud.onrender.com/docs).

1. The `MonsBeing/fitbuddy` GitHub repository is connected to the `fitbuddy-production` Render Blueprint. For a fresh environment, choose **New → Blueprint** in Render and enter the repository URL.
2. The blueprint created the `fitbuddy` web service and `fitbuddy-db` database. The service URL is [https://fitbuddy-xrud.onrender.com](https://fitbuddy-xrud.onrender.com); the generated coach password is available in the service's Environment settings under `ADMIN_PASSWORD`.
3. To enable live Gemini generation, add `GOOGLE_API_KEY` in the Render service's Environment settings, save, and redeploy. Without it, the hosted site still works using the local fallback generator.

**Render free-tier limitation:** the web service can sleep when idle, and a free Postgres database expires after 30 days. Upgrade the Render Postgres plan before that deadline if you need longer-lived user data. Paid database or web-service plans can incur charges; review the current Render pricing before upgrading. Render's free services are intended for previews and hobby use, not production data.

## Test the application manually

1. Visit the home page, fill in a profile, and create a plan. Confirm that all seven days, a tip, and the user ID appear.
2. Submit feedback such as “Add more cardio” or “Include another recovery day.” Confirm that the updated plan appears and the page reports that the feedback was saved.
3. Reload the site, open the coach dashboard, enter the configured credentials, and confirm the user and original/latest plan versions are listed.
4. Check `/health` for `{"status":"ok"}` and use `/docs` to explore the JSON API. For `POST /api/plans`, send JSON like:

   ```json
   {
     "username": "Alex Morgan",
     "user_id": "alex_fit_01",
     "age": 28,
     "weight": 68,
     "goal": "general_fitness",
     "intensity": "medium",
     "experience": "beginner"
   }
   ```

   Send feedback to `POST /api/plans/alex_fit_01/feedback` with `{"user_id":"alex_fit_01","feedback":"Add a little more cardio"}`.

## Project structure

```text
app/
  config.py                 Environment-based settings
  database.py               SQLAlchemy engine and session lifecycle
  gemini_generator.py       Gemini calls and local fallbacks
  main.py                   FastAPI app and startup initialization
  models.py                 User and workout-plan tables
  routes.py                 HTML and JSON endpoints
  schemas.py                Request validation
static/css/styles.css       Responsive interface styling
templates/
  index.html                Profile form
  result.html               Workout plan, tip, and feedback
  all_users.html            Coach dashboard
.env.example                Local configuration template
requirements.txt            Python dependencies
```

The database file `fitbuddy.db` is created automatically on first start. Keep the app bound to localhost for personal development. The coach view uses HTTP Basic authentication; configure a strong password before sharing the app with anyone else. Fitness plans and tips are general wellness information, not medical advice.
