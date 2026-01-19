from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def get_success():
    return {"status": "success"}
