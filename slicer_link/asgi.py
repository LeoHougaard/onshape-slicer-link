"""Container entry point. Exactly one worker owns the SQLite store and job queue."""

from .service import Settings, create_app

app = create_app(Settings.environment())
