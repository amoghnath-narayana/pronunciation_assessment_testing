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
# Note: This uses 'install' instead of 'sync' to preserve transitive dependencies
sync:
    @test -d .venv || uv venv
    uv pip install -r requirements.txt

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

# Update packages respecting existing constraints
update:
    @test -d .venv || uv venv
    uv pip install --upgrade -r requirements.txt
    @echo "Packages updated within constraints"

# Force update all packages to latest versions and freeze to requirements.txt
update-hard:
    @test -d .venv || uv venv
    uv pip install --upgrade streamlit google-generativeai python-dotenv ruff
    uv pip freeze > requirements.txt
    @echo "All packages force-updated to latest versions and frozen to requirements.txt"

# Run the app in development mode with auto-reload
dev:
    uv run streamlit run app.py --server.runOnSave true

# Check if .env file exists
check-env:
    @test -f .env || (echo "Error: .env file not found!" && exit 1)
    @echo "YES - .env file exists"

# Show TTS cache statistics
cache-stats:
    @echo "TTS Cache Statistics:"
    @echo "===================="
    @if [ -f "assets/tts/cache/cache.db" ]; then \
        du -sh assets/tts/cache 2>/dev/null || echo "Cache directory not found"; \
        echo "Database size: $$(du -h assets/tts/cache/cache.db 2>/dev/null | cut -f1)"; \
        echo "Total files: $$(find assets/tts/cache -type f | wc -l | tr -d ' ')"; \
    else \
        echo "Cache not initialized"; \
    fi

# Clear TTS cache
clear-cache:
    @echo "Clearing TTS cache..."
    @rm -rf assets/tts/cache/*
    @echo "TTS cache cleared!"

# Clear all caches (TTS + Python cache)
clear-all: clear-cache clean
    @echo "All caches cleared!"
