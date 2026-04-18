# Archivo para el import de blueprints.
# Los blueprints son una herramienta que permite agrupar rutas en grupos particulares. En este caso, usamos blueprints para distinguir las pantallas correspondientes a cada vista (pública, admin, clínica, y de autenticación.)

from .auth     import auth_bp
from .public   import public_bp
from .clinical import clinical_bp
from .admin    import admin_bp

__all__ = ['auth_bp', 'public_bp', 'clinical_bp', 'admin_bp']
