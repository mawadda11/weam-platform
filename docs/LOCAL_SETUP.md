# Local setup — Windows / PowerShell

## Prerequisites
- Git
- Node.js 20+
- Python 3.12+
- Docker Desktop (recommended for PostgreSQL)

## 1. Copy environment files
From the repository root:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Before any deployment, replace `WEAM_JWT_SECRET` with a long random secret.

## 2. Start PostgreSQL

```powershell
docker compose up -d postgres
```

If Docker is unavailable, tests still use SQLite automatically. The application itself is configured for PostgreSQL by default.

## 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open:
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

### Optional synthetic demo data
From `backend/` with the virtual environment active:

```powershell
python scripts/seed_demo.py
```

Demo login:
- Email: `guardian@weam.demo`
- Password: `WeamDemo123!`

## 4. Frontend
Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## 5. Tests

```powershell
cd backend
pytest -q
```

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Google Sign-In
Email/password works without Google configuration.

To activate Google Sign-In, put the same web Client ID in:
- `backend/.env` → `WEAM_GOOGLE_CLIENT_ID`
- `frontend/.env` → `VITE_GOOGLE_CLIENT_ID`

The Google Cloud OAuth origin must include `http://localhost:5173` for local development.

## Important data rule
Do not enter or commit real child, medical, identity, credential, or API-key data while developing the competition version. Use synthetic data only.
