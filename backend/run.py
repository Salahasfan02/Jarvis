"""Start the Jarvis backend: python run.py"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
