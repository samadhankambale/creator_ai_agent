from fastapi import FastAPI

from app.api.whatsapp_webhook import (
    router as whatsapp_router
)

from app.api.oauth_routes import (
    router as oauth_router
)


app = FastAPI()


@app.get("/")
async def root():

    return {
        "message": "Creator Agent Running"
    }


app.include_router(
    whatsapp_router
)

app.include_router(
    oauth_router
)




# from fastapi import FastAPI
# from app.api.instagram_routes import (
#     router as instagram_router
# )
# from app.api.whatsapp_webhook import (
#     router as whatsapp_router
# )

# from app.api.oauth_routes import (
#     router as oauth_router
# )

# app = FastAPI(
#     title="Creator Agent"
# )

# app.include_router(whatsapp_router)

# app.include_router(oauth_router)

# app.include_router(instagram_router)

# @app.get("/")

# async def root():

#     return {
#         "message": "Creator Agent Running"
#     }