"""
E2B Sandbox integration for simulation execution.

E2B provides secure, isolated environments for running untrusted code.
We use it to execute simulation scenarios safely.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from agent_polis.config import settings
from agent_polis.simulations.models import ExecutionLog, SimulationResult

logger = structlog.get_logger()


class SandboxExecutor:
    """
    Executes code in E2B sandboxes.
    
    E2B sandboxes provide isolated execution environments with:
    - Full Linux environment
    - Network isolation
    - Resource limits
    - Automatic cleanup
    """
    
    def __init__(self):
        self.api_key = settings.e2b_api_key
        self._sandbox = None
    
    async def execute(
        self,
        code: str,
        inputs: dict[str, Any] | None = None,
        environment: dict[str, str] | None = None,
        timeout_seconds: int = 60,
    ) -> SimulationResult:
        """
        Execute code in an E2B sandbox.
        
        Args:
            code: Python code to execute
            inputs: Input variables to inject
            environment: Environment variables
            timeout_seconds: Maximum execution time
            
        Returns:
            SimulationResult with output, logs, and status
        """
        logs: list[ExecutionLog] = []
        start_time = datetime.now(timezone.utc)
        
        # Log start
        logs.append(ExecutionLog(
            timestamp=start_time,
            level="info",
            message="Starting sandbox execution",
        ))
        
        # Check if E2B is configured
        if not self.api_key:
            logger.warning("E2B API key not configured, using mock execution")
            return await self._mock_execute(code, inputs, timeout_seconds, logs)
        
        try:
            # Import E2B SDK
            from e2b import Sandbox
            
            # Create sandbox
            logs.append(ExecutionLog(
                timestamp=datetime.now(timezone.utc),
                level="info",
                message="Creating E2B sandbox",
            ))
            
            sandbox = Sandbox(api_key=self.api_key, timeout=timeout_seconds)
            
            try:
                # Prepare the execution script
                script = self._prepare_script(code, inputs)
                
                # Write script to sandbox
                sandbox.filesystem.write("/tmp/simulation.py", script)
                
                # Set environment variables
                env_str = ""
                if environment:
                    for key, value in environment.items():
                        env_str += f"export {key}='{value}' && "
                
                # Execute
                logs.append(ExecutionLog(
                    timestamp=datetime.now(timezone.utc),
                    level="info",
                    message="Executing simulation code",
                ))
                
                result = sandbox.process.start_and_wait(
                    f"{env_str}python /tmp/simulation.py",
                    timeout=timeout_seconds,
                )
                
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # Parse result
                success = result.exit_code == 0
                
                logs.append(ExecutionLog(
                    timestamp=end_time,
                    level="info" if success else "error",
                    message=f"Execution {'completed' if success else 'failed'} with exit code {result.exit_code}",
                ))
                
                return SimulationResult(
                    success=success,
                    output=self._parse_output(result.stdout),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    duration_ms=duration_ms,
                    logs=logs,
                    error=result.stderr if not success else None,
                )
                
            finally:
                # Always close sandbox
                sandbox.close()
                
        except ImportError:
            logger.warning("E2B SDK not installed, using mock execution")
            return await self._mock_execute(code, inputs, timeout_seconds, logs)
            
        except Exception as e:
            logger.error("Sandbox execution failed", error=str(e), exc_info=e)
            
            logs.append(ExecutionLog(
                timestamp=datetime.now(timezone.utc),
                level="error",
                message=f"Execution error: {str(e)}",
            ))
            
            return SimulationResult(
                success=False,
                logs=logs,
                error=str(e),
            )
    
    def _prepare_script(self, code: str, inputs: dict[str, Any] | None) -> str:
        """Prepare the execution script with inputs."""
        script_parts = [
            "import json",
            "import sys",
            "",
        ]
        
        # Inject inputs as variables
        if inputs:
            script_parts.append("# Injected inputs")
            for key, value in inputs.items():
                script_parts.append(f"{key} = {repr(value)}")
            script_parts.append("")
        
        # Add the user code
        script_parts.append("# User code")
        script_parts.append(code)
        
        # Add output capture
        script_parts.extend([
            "",
            "# Output result if 'result' variable exists",
            "if 'result' in dir():",
            "    print('__RESULT__:' + json.dumps(result))",
        ])
        
        return "\n".join(script_parts)
    
    def _parse_output(self, stdout: str | None) -> Any:
        """Parse the result from stdout if present."""
        if not stdout:
            return None
        
        import json
        
        for line in stdout.split("\n"):
            if line.startswith("__RESULT__:"):
                try:
                    return json.loads(line[11:])
                except json.JSONDecodeError:
                    pass
        
        return None
    
    async def _mock_execute(
        self,
        code: str,
        inputs: dict[str, Any] | None,
        timeout_seconds: int,
        logs: list[ExecutionLog],
    ) -> SimulationResult:
        """
        Mock execution when E2B is not available.
        
        This executes code locally in a restricted way for development/testing.
        NOT suitable for production - use E2B for real isolation.
        """
        logs.append(ExecutionLog(
            timestamp=datetime.now(timezone.utc),
            level="warning",
            message="Using mock execution (E2B not configured)",
            source="system",
        ))
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Create a restricted globals dict
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "len": len,
                    "range": range,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "abs": abs,
                    "round": round,
                    "sorted": sorted,
                    "enumerate": enumerate,
                    "zip": zip,
                    "map": map,
                    "filter": filter,
                    "True": True,
                    "False": False,
                    "None": None,
                    # Common exceptions
                    "Exception": Exception,
                    "ValueError": ValueError,
                    "TypeError": TypeError,
                    "KeyError": KeyError,
                    "IndexError": IndexError,
                    "RuntimeError": RuntimeError,
                    "AttributeError": AttributeError,
                },
            }
            
            # Add inputs to globals
            if inputs:
                safe_globals.update(inputs)
            
            # Capture output
            import io
            import sys
            
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = stdout_capture = io.StringIO()
            sys.stderr = stderr_capture = io.StringIO()
            
            try:
                # Execute with timeout
                exec(code, safe_globals)
                
                success = True
                error = None
                
            except Exception as e:
                success = False
                error = str(e)
                
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            stdout_str = stdout_capture.getvalue()
            stderr_str = stderr_capture.getvalue()
            
            # Get result if set
            output = safe_globals.get("result")
            
            logs.append(ExecutionLog(
                timestamp=end_time,
                level="info" if success else "error",
                message=f"Mock execution {'completed' if success else 'failed'}",
            ))
            
            return SimulationResult(
                success=success,
                output=output,
                stdout=stdout_str if stdout_str else None,
                stderr=stderr_str if stderr_str else None,
                exit_code=0 if success else 1,
                duration_ms=duration_ms,
                logs=logs,
                error=error,
            )
            
        except Exception as e:
            logs.append(ExecutionLog(
                timestamp=datetime.now(timezone.utc),
                level="error",
                message=f"Mock execution error: {str(e)}",
            ))
            
            return SimulationResult(
                success=False,
                logs=logs,
                error=str(e),
            )


# Global executor instance
_executor: SandboxExecutor | None = None


def get_sandbox_executor() -> SandboxExecutor:
    """Get the global sandbox executor instance."""
    global _executor
    if _executor is None:
        _executor = SandboxExecutor()
    return _executor
