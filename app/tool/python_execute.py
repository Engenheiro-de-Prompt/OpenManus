import multiprocessing
import multiprocessing
import sys
import os
from io import StringIO
from typing import Dict, Optional
import traceback # Added import traceback
import ast # Added import ast
from app.logger import logger # Added import logger

from app.tool.base import BaseTool


class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = ("Executes a Python code string directly on the host machine (not in the sandbox). "
                        "Captures and returns stdout, stderr, and an exit_code. "
                        "Use 'working_directory' to specify the execution path, especially if the code interacts with local files. "
                        "Avoid relative file paths if 'working_directory' is not set, as code runs in the agent's main process environment. "
                        "For file-based script execution or sandboxed execution, use 'sandbox_python_executor'. "
                        "This tool is best for simple, self-contained code snippets.")
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "working_directory": { # Novo parâmetro
                "type": "string",
                "description": "Optional. The working directory in which to execute the code. Defaults to the agent's main process working directory if not specified.",
                "nullable": True
            }
        },
        "required": ["code"],
    }

    def _run_code(self, code: str, result_dict: dict, safe_globals: dict, working_directory: Optional[str] = None) -> None:
        original_stdout = sys.stdout
        original_stderr = sys.stderr # Capture original stderr
        original_cwd = os.getcwd()
        cwd_changed_successfully = False
        output_buffer = StringIO()
        error_buffer = StringIO() # Buffer for stderr
        sys.stdout = output_buffer
        sys.stderr = error_buffer # Redirect stderr

        try:
            if working_directory:
                if os.path.isdir(working_directory):
                    os.chdir(working_directory)
                    cwd_changed_successfully = True
                else:
                    # This error will be caught by the except block
                    raise FileNotFoundError(f"Specified working_directory '{working_directory}' does not exist or is not a directory.")

            exec(code, safe_globals, safe_globals)
            result_dict["stdout"] = output_buffer.getvalue()
            result_dict["stderr"] = error_buffer.getvalue()
            result_dict["exit_code"] = 0
            result_dict["success"] = True
            result_dict["observation"] = result_dict["stdout"] # Keep observation as stdout for compatibility
        except Exception as e:
            stderr_capture = error_buffer.getvalue()
            exception_traceback = traceback.format_exc()
            result_dict["stdout"] = output_buffer.getvalue() # Capture any stdout before the error
            result_dict["stderr"] = (stderr_capture + "\n" + str(e) + "\n" + exception_traceback).strip()
            result_dict["exit_code"] = 1
            result_dict["success"] = False
            result_dict["observation"] = result_dict["stderr"] # Keep observation as stderr on error
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr # Restore original stderr
            if cwd_changed_successfully:
                os.chdir(original_cwd)

    async def execute(
        self,
        code: str,
        timeout: int = 5, # Mantido timeout padrão
        working_directory: Optional[str] = None,
    ) -> Dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            timeout (int): Execution timeout in seconds.
            working_directory (Optional[str]): The working directory for code execution.

        Returns:
            Dict: Contains 'stdout', 'stderr', 'exit_code', 'success' status, and 'observation'.
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            logger.error(f"SyntaxError in provided code: {e}\n{traceback.format_exc()}")
            error_details = f"SyntaxError: {str(e)}\n{traceback.format_exc()}"
            return {
                "stdout": "",
                "stderr": error_details,
                "exit_code": 1, # Consistent with other execution failures
                "success": False,
                "observation": error_details
            }

        with multiprocessing.Manager() as manager:
            result = manager.dict({"stdout": "", "stderr": "", "exit_code": -1, "success": False, "observation": ""})
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": __builtins__}
            else:
                safe_globals = {"__builtins__": __builtins__.__dict__.copy()}
            
            # Passar working_directory para o target _run_code
            proc = multiprocessing.Process(
                target=self._run_code, args=(code, result, safe_globals, working_directory) 
            )
            proc.start()
            proc.join(timeout)

            # timeout process
            if proc.is_alive():
                proc.terminate()
                proc.join(1) # Dar um segundo para o terminate
                # Adicionar working_directory à mensagem de timeout se ele foi especificado
                timeout_message = f"Execution timeout after {timeout} seconds"
                if working_directory:
                    timeout_message += f" (in working_directory: '{working_directory}')"
                return {"stdout": "", "stderr": timeout_message, "exit_code": 1, "success": False, "observation": timeout_message}
            return dict(result)
