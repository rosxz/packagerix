"""Tool to try building the current packaging expression."""

from vibenix.ccl_log import get_logger, log_function_call

from abc import ABC

class build_package(ABC):
    @log_function_call("build_package")
    def build_package():
        """Tool to try building the current packaging expression."""
        print(f"📞 Function called: build_package")
        return build_package._build_package()
    
    @staticmethod
    def _build_package():
        """Tool to try building the current packaging expression."""
        return None
