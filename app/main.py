from fastapi import FastAPI
from app.api.whatsapp_webhook import router as webhook_router
from app.api.linkedin_oauth_routes import router as linkedin_router
from app.api.oauth_routes import router as meta_router

app = FastAPI(title="Creator Agent")


@app.get("/")
async def root():
    return {"message": "Creator Agent Running"}


app.include_router(webhook_router)
app.include_router(linkedin_router)
app.include_router(meta_router)   # handles /oauth/meta/* and /oauth/threads/*