from fastapi import FastAPI

app = FastAPI(
    title="GuardianX API",
    description="GuardianX Backend API",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {
        "application": "GuardianX",
        "status": "Running",
        "version": "1.0.0"
    }