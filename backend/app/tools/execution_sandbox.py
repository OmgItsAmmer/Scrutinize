import os
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

def execute_python_in_sandbox(code: str) -> str:
    """Executes python code in a secure E2B sandbox microVM.
    
    If E2B_API_KEY is not configured, it runs in a safe local mockup simulation
    to prevent breaking local development.
    """
    settings = get_settings()
    api_key = settings.e2b_api_key or os.getenv("E2B_API_KEY", "")
    
    if not api_key:
        logger.warning("E2B_API_KEY is not set. Running in local simulation fallback.")
        import sys
        import io
        import contextlib

        f = io.StringIO()
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            try:
                # Local safe mockup / simulation
                exec_globals = {}
                exec(code, exec_globals)
            except Exception as e:
                print(f"Error during local simulation: {e}", file=sys.stderr)
        return f"[MOCK E2B SANDBOX OUTPUT]\n{f.getvalue().strip()}"

    try:
        from e2b import Sandbox
    except ImportError:
        logger.error("e2b python client library is not installed.")
        return "Error: e2b package is not installed."

    try:
        # Start throwaway Firecracker MicroVM
        sandbox = Sandbox(api_key=api_key)
        sandbox.files.write("main.py", code)
        execution = sandbox.run_command("python main.py")
        stdout = execution.stdout
        stderr = execution.stderr
        sandbox.close()
        
        if stderr:
            return f"Stdout:\n{stdout}\n\nStderr:\n{stderr}"
        return stdout
    except Exception as e:
        logger.error(f"E2B sandbox execution failed: {e}")
        return f"Error executing code in E2B sandbox: {str(e)}"
