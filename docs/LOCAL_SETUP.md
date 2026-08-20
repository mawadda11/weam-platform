# Local setup

## Prerequisites
- Git
- Node.js 20+
- Python 3.12+
- Docker Desktop (recommended for PostgreSQL)

## 1. Database
From repository root:

```bash
docker compose up -d postgres
```

## 2. Backend
Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:WEAM_DATABASE_URL="postgresql+psycopg://weam:weam@localhost:5432/weam"
uvicorn app.main:app --reload
```

Open: `http://localhost:8000/docs`

Health check: `http://localhost:8000/api/v1/health`

## 3. Frontend
Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

## 4. Tests
Backend:

```powershell
cd backend
pytest
```

Frontend typecheck:

```powershell
cd frontend
npm run typecheck
```

## Important
Never commit `.env`, API keys, medical records, identity numbers, or real child data.
