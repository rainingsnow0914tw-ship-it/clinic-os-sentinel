"""
集中匯出所有 routers，讓 main.py 只要一行 import。
"""
from app.routes.auth import router as auth_router
from app.routes.patients import router as patients_router
from app.routes.visits import router as visits_router
from app.routes.drugs import router as drugs_router
from app.routes.prescriptions import router as prescriptions_router
from app.routes.invoices import router as invoices_router
from app.routes.documents import router as documents_router
from app.routes.ai import router as ai_router
from app.routes.agent_tasks import router as agent_tasks_router
from app.routes.reports import router as reports_router
from app.routes.sentinel import router as sentinel_router
from app.routes.sentinel_patients import router as sentinel_patients_router
from app.routes.sentinel_review import router as sentinel_review_router
from app.routes.sentinel_watchlist import router as sentinel_watchlist_router
from app.routes.sentinel_drugs import router as sentinel_drugs_router

__all__ = [
    "auth_router",
    "patients_router",
    "visits_router",
    "drugs_router",
    "prescriptions_router",
    "invoices_router",
    "documents_router",
    "ai_router",
    "agent_tasks_router",
    "reports_router",
    "sentinel_router",
    "sentinel_patients_router",
    "sentinel_review_router",
    "sentinel_watchlist_router",
    "sentinel_drugs_router",
]
