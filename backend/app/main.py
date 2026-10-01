"""Điểm vào uvicorn: uvicorn app.main:app"""

import logging

from .api import create_app
from .config import load_settings
from .db import Database
from .extraction import provider_for
from .storage import ImmutableStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = load_settings()
app = create_app(settings, Database(settings.database_url), ImmutableStorage(settings.storage_dir),
                 provider_for(settings.ocr_provider))
