from enum import Enum

class TemplateType(Enum):
    """Enum of available Nix package template types."""
    
    # Generic template for C/C++ and other languages without specific templates
    GENERIC = "package"
    
    # JavaScript/Node.js templates
    NPM = "regular-npm"
    PNPM = "node-with-pnmp"
    
    # Python templates
    PYTHON = "python"
    PYTHON_UV = "python-uv"
    
    # Other language templates
    GO = "go"
    RUST = "rust"
    DART = "dart"
    FLUTTER = "flutter"
    ZIG = "zig"
