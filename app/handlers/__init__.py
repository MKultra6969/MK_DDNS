from .access import router as access_router
from .menu import router as menu_router
from .providers import router as providers_router
from .records import router as records_router

__all__ = [
    "access_router",
    "menu_router",
    "providers_router",
    "records_router",
]
