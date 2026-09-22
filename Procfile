web: uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8000}
worker: python -m src.groww_pulse.main --weeks 8
