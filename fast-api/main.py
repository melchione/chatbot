import os
import sentry_sdk

from fastapi import FastAPI, Depends, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from langtrace_python_sdk import langtrace

from app.routes.workflows import workflows_router
from app.routes.admin import admin_router
from app.routes.writer import writer_router
from app.routes.format import format_router
from app.routes.datas import datas_router
from app.routes.cron import cron_router

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

langtrace.init(api_key=os.getenv("LANGTRACE_API_KEY"))

app = FastAPI(
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Récupérer l'origine de la requête
        origin = request.headers.get("origin")

        if not origin:
            return await call_next(request)

        try:
            # Retirer le protocol et www (http:// ou https://)

            # Gérer les requêtes préflight OPTIONS
            if request.method == "OPTIONS":
                return Response(
                    status_code=204,
                    content="",
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Visitor-Token, User-Agent",
                        "Access-Control-Max-Age": "3600",  # Cache pour 1 heure
                    },
                )

            # Pour les autres requêtes
            response = await call_next(request)

            # Ajouter les headers CORS
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-Visitor-Token, User-Agent"
            )

            return response

        except Exception as err:
            print(f"Error in CORS middleware: {str(err)}")
            return await call_next(request)


# Ajouter le middleware personnalisé
app.add_middleware(DynamicCORSMiddleware)

app.include_router(workflows_router, prefix="/workflows", tags=["Workflows"])
app.include_router(writer_router, prefix="/writers", tags=["Writers"])
app.include_router(format_router, prefix="/formats", tags=["Format"])
app.include_router(datas_router, prefix="/datas", tags=["Datas"])
app.include_router(admin_router, prefix="", tags=["Admin"])
app.include_router(cron_router, prefix="/cron", tags=["Cron"])
