# Nutrisage

Nutrisage is a Flask-based food tracking application for logging meals, reviewing nutrition history, exploring dashboard insights, and checking AI-powered daily calorie forecasts.

## Features

- Daily food logging with quantity-aware meal entries
- Nutrition history with calories, protein, carbs, and fat totals
- Dashboard analytics and chart-based intake visualization
- AI tracker page for daily intake forecasting and historical forecast review
- Authentication with login and registration flows
- Admin/add-food flow for managing food items

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- SQLite for local development
- Bootstrap, HTML, CSS, and vanilla JavaScript

## Project Structure

```text
rootproject/
|-- foodtracker/
|   |-- ai/              # AI tracker routes and forecasting logic
|   |-- auth/            # Authentication routes
|   |-- dashboard/       # Dashboard routes and chart APIs
|   |-- main/            # Main app routes for logs and food entries
|   |-- ml_models/       # Model training utilities
|   |-- static/          # CSS, JS, images, and Bootstrap assets
|   |-- templates/       # Jinja templates
|   |-- __init__.py      # Flask app factory
|   |-- extensions.py    # Shared extension instances
|   `-- models.py        # Database models
|-- migrations/          # Flask-Migrate / Alembic files
|-- instance/            # Local runtime database files (not committed)
|-- requirements.txt
`-- README.md
```

## Getting Started

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Set Flask environment values

The repo already includes a `.flaskenv` for local development:

```env
FLASK_APP=foodtracker
FLASK_ENV=development
FLASK_DEBUG=1
```

### 4. Run the app

```powershell
flask run
```

Open the app at:

`http://127.0.0.1:5000`

## Notes

- Local SQLite data is created in the `instance/` folder.
- The trained prediction model file is stored under `foodtracker/models/`.
- Runtime folders like `venv/`, `instance/`, and cache files are ignored from the repo.
