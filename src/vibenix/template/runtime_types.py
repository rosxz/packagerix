from enum import Enum

class RuntimeType(Enum):
    """Enum of available runtime types for templates."""
    # Generic libraries (.so, .a)
    GENERIC = "generic"
    
    PYTHON = "python"
