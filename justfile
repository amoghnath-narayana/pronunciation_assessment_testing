# Pronunciation Assessment API - Just Commands
# Requires: just, uv

# Default recipe to display available commands
default:
    @just --list

# Install dependencies using uv (creates venv if needed)
install:
    @test -d .venv || uv venv
    uv pip install -r requirements.txt

# Sync dependencies (install/update to match requirements.txt exactly)
# Note: This uses 'install' instead of 'sync' to preserve transitive dependencies
sync:
    @test -d .venv || uv venv
    uv pip install -r requirements.txt

# Start the FastAPI server (development mode with auto-reload)
run:
    @echo "Starting API server at http://localhost:8000"
    @echo "API docs available at http://localhost:8000/docs"
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Clear Python cache files and directories
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.py~" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    @echo "Python cache cleaned!"

# Clean and reinstall dependencies
reset: clean
    @test -d .venv || uv venv
    uv pip install -r requirements.txt

# Check Python code with ruff (if installed)
lint:
    uv run ruff check . || echo "ruff not installed, skipping lint"

# Format Python code with ruff (if installed)
format:
    uv run ruff format . || echo "ruff not installed, skipping format"

# Show current Python environment info
info:
    @echo "Python version:"
    @uv run python --version
    @echo "\nInstalled packages:"
    @uv pip list

# Create a new virtual environment with uv
venv:
    uv venv

# Freeze current dependencies to requirements.txt
freeze:
    @test -d .venv || uv venv
    uv pip freeze > requirements.txt
    @echo "Dependencies frozen to requirements.txt"

# Update packages respecting existing constraints
update:
    @test -d .venv || uv venv
    uv pip install --upgrade -r requirements.txt
    @echo "Packages updated within constraints"

# Force update all packages to latest versions and freeze to requirements.txt
update-hard:
    @test -d .venv || uv venv
    uv pip install --upgrade fastapi uvicorn google-generativeai python-dotenv ruff pydantic
    uv pip freeze > requirements.txt
    @echo "All packages force-updated to latest versions and frozen to requirements.txt"

# Run the app in development mode with auto-reload
dev:
    @echo "Starting API server in dev mode at http://localhost:8000"
    @echo "API docs: http://localhost:8000/docs"
    @echo "Logfire enabled for local logging"
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# Check if .env file exists
check-env:
    @test -f .env || (echo "Error: .env file not found!" && exit 1)
    @echo "YES - .env file exists"

# Clear TTS cache