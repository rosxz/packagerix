"""
Signal-safe CCL logging implementation.
"""

import signal
import atexit
from typing import Optional

from .ccl_log import get_logger, close_logger


def ensure_log_cleanup():
    """Ensure log is properly closed on exit."""
    try:
        logger = get_logger()
        # Log final cost before closing
        from vibenix.packaging_flow.litellm_callbacks import end_stream_logger
        if end_stream_logger.total_cost > 0:
            logger.log_session_end(
                success=False,  # Interrupted
                total_iterations=0,  # Unknown
                total_cost=end_stream_logger.total_cost
            )
        logger.close()
    except Exception:
        # Ignore errors during cleanup
        pass


def setup_safe_logging():
    """Set up signal handlers to ensure logs are written on termination."""
    # Register cleanup function for normal exit
    atexit.register(ensure_log_cleanup)
    
    # Handle common termination signals
    def signal_handler(signum, frame):
        ensure_log_cleanup()
        # Re-raise the signal to allow normal termination
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)
    
    # Register handlers for common termination signals
    for sig in [signal.SIGTERM, signal.SIGINT]:
        try:
            signal.signal(sig, signal_handler)
        except OSError:
            # Some signals may not be available on all platforms
            pass