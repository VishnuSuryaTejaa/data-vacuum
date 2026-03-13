import asyncio
import os
import sys
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Data Vacuum Dashboard")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure output directory exists
os.makedirs("output", exist_ok=True)

class RunRequest(BaseModel):
    prompt: str
    labels: str
    max_queries: int = 5
    include_comments: bool = False

# Store active processes
active_processes = {}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/api/run")
async def start_run(req: RunRequest):
    exec_id = str(uuid.uuid4())
    
    # Define unique output path for this run
    output_path = f"output/dataset_{exec_id}.parquet"
    
    # Build command
    cmd = [
        sys.executable, "main.py",
        "--prompt", req.prompt,
        "--labels", req.labels,
        "--max-queries", str(req.max_queries),
        "--output", output_path
    ]
    if req.include_comments:
        cmd.append("--include-comments")
    
    # Start subprocess
    # We use PYTHONUNBUFFERED=1 to ensure live streaming
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Force rich to use colors (so we can parse ansi in the frontend)
    env["FORCE_COLOR"] = "1"
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        limit=1024 * 1024 * 5  # 5MB buffer for long \r progress bars
    )
    
    active_processes[exec_id] = {
        "process": process,
        "output_path": output_path
    }
    
    return {"exec_id": exec_id}

@app.get("/api/stream/{exec_id}")
async def stream_logs(exec_id: str, request: Request):
    if exec_id not in active_processes:
        return HTMLResponse("Execution ID not found", status_code=404)
        
    process = active_processes[exec_id]["process"]
    
    async def log_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                    
                line = await process.stdout.readline()
                if not line:
                    break
                    
                # Decode line and yield as SSE
                text = line.decode('utf-8', errors='replace').rstrip('\n')
                # If there are carriage returns from rich progress bars, only send the final frame
                if '\r' in text:
                    text = text.rsplit('\r', 1)[-1]
                # Yield in SSE format
                yield f"data: {text}\n\n"
                
            await process.wait()
            # Send an indicator that process finished and whether it was successful
            exit_code = process.returncode
            yield f"event: done\ndata: {exit_code}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"
            
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/download/{exec_id}")
async def download_file(exec_id: str, type: str = "csv"):
    if exec_id not in active_processes:
        return HTMLResponse("Execution ID not found", status_code=404)
        
    base_output = active_processes[exec_id]["output_path"]
    
    if type == "parquet":
        file_path = base_output
        filename = f"training_dataset_{exec_id}.parquet"
        media_type = "application/vnd.apache.parquet"
    else:
        # Default to CSV
        file_path = str(Path(base_output).with_suffix(".csv"))
        filename = f"training_dataset_{exec_id}.csv"
        media_type = "text/csv"
        
    if not os.path.exists(file_path):
        return HTMLResponse("File not generated", status_code=404)
        
    return FileResponse(path=file_path, filename=filename, media_type=media_type)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
