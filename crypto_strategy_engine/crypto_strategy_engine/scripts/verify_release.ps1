$ErrorActionPreference = "Stop"
python -m compileall -q src tests
pytest
ruff check src tests
mypy src
python -m crypto_strategy_engine schema-hash
