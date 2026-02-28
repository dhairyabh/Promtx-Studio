from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, uuid

from services.prompt import handle_prompt
from database import get_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/outputs", StaticFiles(directory=os.path.join(BASE_DIR, "outputs")), name="outputs")

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/process-video/")
async def process_video_endpoint(
    video: UploadFile = File(None),
    prompt: str = Form(...)
):
    uid = str(uuid.uuid4())
    
    if video:
        input_path = os.path.join(UPLOAD_DIR, f"{uid}_{video.filename}")
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
    else:
        # For generation, we don't need an input video
        input_path = None # Correctly pass None for handle_prompt

    output_path = os.path.join(OUTPUT_DIR, f"processed_{uid}.mp4")

    from starlette.concurrency import run_in_threadpool
    try:
        # Assuming 'handle_prompt' is being renamed to 'process_user_instruction'
        # and 'video_path' in the instruction refers to 'input_path'
        # and the trailing arguments were meant to be passed to the function.
        final_path = await run_in_threadpool(handle_prompt, prompt, input_path, output_path)
        print(f"DEBUG: handle_prompt returned final_path='{final_path}'")
        
        video_url = f"/outputs/{os.path.basename(final_path)}"
        print(f"Result ready: {final_path} -> {video_url}")

        response_data = {"video_url": video_url}
        
        # If the output is a text file (summary), read and return its content
        if final_path.endswith(".txt"):
            try:
                with open(final_path, "r", encoding="utf-8") as f:
                    response_data["summary"] = f.read()
            except Exception as e:
                print(f"Error reading summary file: {e}")
                response_data["summary"] = "Error reading summary content."

        return response_data
    except Exception as e:
        error_msg = str(e)
        print(f"Processing Error: {error_msg}")
        return {
            "error": error_msg
        }

from pydantic import BaseModel
from datetime import datetime

class Feedback(BaseModel):
    name: str
    email: str
    message: str

@app.post("/api/feedback")
async def submit_feedback(feedback: Feedback):
    db = get_db()
    if db is None:
        return {"error": "Database connection failed. Please check MONGODB_URI."}
        
    feedback_data = feedback.dict()
    feedback_data["timestamp"] = datetime.utcnow()
    
    try:
        # Insert into the 'feedback' collection
        db.feedback.insert_one(feedback_data)
        return {"success": True, "message": "Feedback submitted successfully!"}
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return {"error": "Failed to save feedback."}
