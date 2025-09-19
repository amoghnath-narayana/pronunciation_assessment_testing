# Pronunciation Coach - Just Commands
# Requires: just, uv

# Default recipe to display available commands
default:
    @just --list

# Install dependencies using uv (creates venv if needed)
install:
    @test -d .venv || uv venv
    uv pip install -r requirements.txt

# Sync dependencies (install/update to match requirements.txt exactly)
sync:
    @test -d .venv || uv venv
    uv pip sync requirements.txt

# Start the Streamlit application
run:
    uv run streamlit run app.py

# Start the Streamlit application with custom port
run-port PORT:
    uv run streamlit run app.py --server.port {{PORT}}

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

# Run the app in development mode with auto-reload
dev:
    uv run streamlit run app.py --server.runOnSave true

# Check if .env file exists
check-env:
    @test -f .env || (echo "Error: .env file not found!" && exit 1)
    @echo "YES - .env file exists"
