from .auth import auth_bp
from .public import public_bp
from .clinical import clinical_bp
from .admin import admin_bp

__all__ = ['auth_bp', 'public_bp', 'clinical_bp', 'admin_bp']
