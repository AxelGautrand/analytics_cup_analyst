"""Registration de tous les callbacks."""
from src.core.logging_config import logger

def register_all_callbacks(app):
    """Register all callbacks from different modules."""
    
    # Import and registration of each module
    from . import callbacks

    
    # Registration
    callbacks.register_callbacks(app)

    logger.info("✅ All callbacks registered successfully")