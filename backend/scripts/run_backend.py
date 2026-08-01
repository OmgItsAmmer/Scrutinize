import sys
import os
import subprocess
import threading
import time
import shutil

# Colored prefixes using ANSI escape codes
COLOR_RESET = "\033[0m"
COLOR_API = "\033[36m"      # Cyan
COLOR_WORKER = "\033[33m"   # Yellow
COLOR_PHOENIX = "\033[35m"  # Magenta
COLOR_SYSTEM = "\033[32m"   # Green

def log(prefix, color, message):
    sys.stdout.write(f"{color}{prefix:<9} | {COLOR_RESET}{message}\n")
    sys.stdout.flush()

def stream_reader(pipe, prefix, color):
    try:
        with pipe:
            for line in iter(pipe.readline, ""):
                log(prefix, color, line.rstrip("\r\n"))
    except Exception as e:
        log(prefix, color, f"Error reading logs: {e}")

def resolve_command(cmd_name):
    # Check if executable exists in the same directory as the python interpreter or its Scripts/bin subdirectories
    py_dir = os.path.dirname(sys.executable)
    dirs_to_check = [
        py_dir,
        os.path.join(py_dir, "Scripts"),
        os.path.join(py_dir, "bin"),
        # In case the interpreter is in a subfolder
        os.path.join(os.path.dirname(py_dir), "Scripts"),
        os.path.join(os.path.dirname(py_dir), "bin"),
    ]
    for d in dirs_to_check:
        for ext in ("", ".exe", ".cmd", ".bat"):
            candidate = os.path.join(d, cmd_name + ext)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    
    # Fallback to system PATH
    resolved = shutil.which(cmd_name)
    if resolved:
        return resolved
        
    return cmd_name

def main():
    # 1. Start Docker services (Qdrant & Redis)
    log("System", COLOR_SYSTEM, "Starting Docker services (Qdrant & Redis)...")
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["docker", "compose", "up", "-d", "qdrant", "redis"], cwd=parent_dir, check=False)
    except Exception as e:
        log("System", COLOR_SYSTEM, f"Warning: Failed to run docker-compose: {e}")

    # 2. Resolve commands
    api_cmd = [resolve_command("uvicorn"), "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    worker_cmd = [resolve_command("celery"), "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--pool=solo"]
    phoenix_cmd = [resolve_command("phoenix"), "serve"]

    log("System", COLOR_SYSTEM, f"Resolved API command: {' '.join(api_cmd)}")
    log("System", COLOR_SYSTEM, f"Resolved Worker command: {' '.join(worker_cmd)}")
    log("System", COLOR_SYSTEM, f"Resolved Phoenix command: {' '.join(phoenix_cmd)}")

    # 3. Start subprocesses
    active_processes = {}
    threads = []

    try:
        # Start API
        log("System", COLOR_SYSTEM, "Starting API (uvicorn)...")
        active_processes["API"] = subprocess.Popen(
            api_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )
        
        # Start Worker
        log("System", COLOR_SYSTEM, "Starting Celery Worker...")
        active_processes["Worker"] = subprocess.Popen(
            worker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )

        # Start Phoenix
        log("System", COLOR_SYSTEM, "Starting Phoenix Serve...")
        active_processes["Phoenix"] = subprocess.Popen(
            phoenix_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )

        # 4. Start log reader threads
        colors = {
            "API": COLOR_API,
            "Worker": COLOR_WORKER,
            "Phoenix": COLOR_PHOENIX
        }
        for name, proc in active_processes.items():
            t = threading.Thread(target=stream_reader, args=(proc.stdout, name, colors[name]), daemon=True)
            t.start()
            threads.append(t)

        # 5. Monitor processes
        log("System", COLOR_SYSTEM, "All services started. Press Ctrl+C to stop.")
        while True:
            for name, proc in list(active_processes.items()):
                ret = proc.poll()
                if ret is not None:
                    log("System", COLOR_SYSTEM, f"Process {name} exited unexpectedly with code {ret}")
                    raise RuntimeError(f"{name} terminated")
            time.sleep(0.5)

    except (KeyboardInterrupt, SystemExit):
        log("System", COLOR_SYSTEM, "KeyboardInterrupt received. Stopping all processes...")
    except Exception as e:
        log("System", COLOR_SYSTEM, f"Error encountered: {e}. Shutting down all processes...")
    finally:
        # 6. Graceful shutdown
        for name, proc in active_processes.items():
            if proc.poll() is None:
                log("System", COLOR_SYSTEM, f"Terminating {name}...")
                try:
                    proc.terminate()
                except Exception:
                    pass
        
        # Wait up to 3 seconds for graceful shutdown
        start_time = time.time()
        while time.time() - start_time < 3:
            if all(proc.poll() is not None for proc in active_processes.values()):
                break
            time.sleep(0.1)

        # Force kill any remaining processes
        for name, proc in active_processes.items():
            if proc.poll() is None:
                log("System", COLOR_SYSTEM, f"Killing {name}...")
                try:
                    proc.kill()
                except Exception:
                    pass

        log("System", COLOR_SYSTEM, "Shutdown complete.")

if __name__ == "__main__":
    main()
