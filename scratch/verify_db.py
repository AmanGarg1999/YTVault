from src.storage.sqlite_store import SQLiteStore
from src.config import get_settings
import json

settings = get_settings()
db = SQLiteStore(settings["sqlite"]["path"])
print(f"Has update_blueprint_progress: {hasattr(db, 'update_blueprint_progress')}")
if hasattr(db, 'update_blueprint_progress'):
    import inspect
    print(inspect.getsource(db.update_blueprint_progress))
db.close()
