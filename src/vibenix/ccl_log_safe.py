"""
Signal-safe CCL logging implementation.
"""

import signal
import atexit
import threading
from typing import Optional

from .ccl_log import get_logger, close_logger


def ensure_log_cleanup(signal_name: Optional[str] = None):
    """Ensure log is properly closed on exit.
    
    Args:
        signal_name: Name of the signal that caused termination, or None for normal exit
    """
    try:
        logger = get_logger()
        # Log session end with signal information
        from vibenix.packaging_flow.litellm_callbacks import end_stream_logger
        logger.log_session_end(
            signal=signal_name,
            total_cost=end_stream_logger.total_cost if end_stream_logger.total_cost > 0 else None
        )
        close_logger()
    except Exception:
        # Ignore errors during cleanup
        pass


def setup_safe_logging():
    """Set up signal handlers to ensure logs are written on termination."""
    # Register cleanup function for normal exit
    atexit.register(ensure_log_cleanup)
    
    # Handle common termination signals
    def signal_handler(signum, frame):
        # Convert signal number to name
        signal_name = signal.Signals(signum).name
        ensure_log_cleanup(signal_name)
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
    
    # Set up timeout (default 1800 seconds = 30 minutes, configurable via env var)
    import os
    timeout_seconds = int(os.environ.get('VIBENIX_TIMEOUT_SECONDS', '1800'))
    
    if timeout_seconds > 0:
        def timeout_handler():
            """Handler for the timeout."""
            ensure_log_cleanup("TIMEOUT")
            # Force exit the entire process immediately
            import os
            os._exit(124)  # Exit code 124 is commonly used for timeouts
        
        # Start the timeout timer
        timeout_timer = threading.Timer(float(timeout_seconds), timeout_handler)
        timeout_timer.daemon = True  # Ensure it doesn't prevent program exit
        timeout_timer.start()
        
        # Store the timer reference so it can be cancelled if needed
        import builtins
        if not hasattr(builtins, '_vibenix_timeout_timer'):
            builtins._vibenix_timeout_timer = timeout_timer
        
        # Log that timeout is set
        try:
            from vibenix.ui.logging_config import logger
            logger.info(f"Timeout set to {timeout_seconds} seconds")
        except:
            pass