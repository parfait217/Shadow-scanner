from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models so they are registered with SQLAlchemy
from .user import User
from .project import Project
from .scan import Scan
from .asset import Asset
from .service import Service
from .vulnerability import Vulnerability
from .finding import Finding
from .employee import Employee
from .breach import Breach
from .alert import Alert
from .audit_log import AuditLog
