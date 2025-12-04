"""VM testing tool using nixos-shell for headless package testing."""

import logging
import pty
import socket
import subprocess
import os
import time
from typing import Optional

import paramiko

from vibenix.ccl_log import log_function_call

logging.getLogger("paramiko").setLevel(logging.CRITICAL)
logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL)


# SSH connection settings
SSH_HOST = "localhost"
SSH_PORT = 2222
SSH_USER = "test"
SSH_PASSWORD = "test"


class VMSession:
    """Represents an active nixos-shell VM session."""
    
    def __init__(self, process: subprocess.Popen, master_fd: int):
        self.process = process
        self.master_fd = master_fd
        self.booted = False
        self.ssh: Optional[paramiko.SSHClient] = None
    
    def is_running(self) -> bool:
        """Check if VM process is running."""
        return self.process is not None and self.process.poll() is None
    
    def read_output(self) -> str:
        """Read available output from VM process."""
        import select
        output = []
        while True:
            readable, _, _ = select.select([self.master_fd], [], [], 0.1)
            if not readable:
                break
            try:
                data = os.read(self.master_fd, 4096)
                if not data:
                    break
                output.append(data.decode('utf-8', errors='replace'))
            except OSError:
                break
        return ''.join(output)
    
    def connect_ssh(self) -> bool:
        """Try to establish SSH connection to VM."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                SSH_HOST,
                port=SSH_PORT,
                username=SSH_USER,
                password=SSH_PASSWORD,
                timeout=5,
                allow_agent=False,
                look_for_keys=False,
            )
            self.ssh = client
            return True
        except Exception:
            return False
    
    def run_command(self, command: str, timeout: float = 30) -> str:
        """Run a command via SSH and return output."""
        if not self.ssh:
            if not self.connect_ssh():
                return "Error: SSH not connected"
        
        assert self.ssh is not None  # Type narrowing for type checker
        try:
            # Use get_transport().open_session() to avoid PTY allocation
            # which triggers profile scripts that call resize
            transport = self.ssh.get_transport()
            if transport is None or not transport.is_active():
                # Connection dropped, try to reconnect
                self.ssh.close()
                self.ssh = None
                if not self.connect_ssh():
                    return "Error: SSH connection lost and reconnect failed"
                assert self.ssh is not None
                transport = self.ssh.get_transport()
                if transport is None:
                    return "Error: SSH transport not available after reconnect"
            
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.exec_command(command)
            
            # Read output
            output = channel.recv(65536).decode('utf-8', errors='replace')
            errors = channel.recv_stderr(65536).decode('utf-8', errors='replace')
            channel.close()
            
            result = (output + errors).rstrip() if errors else output.rstrip()
            
            # Filter out resize error and limit output
            lines = result.split('\n')
            lines = [l for l in lines if not l.startswith("resize:  can't open")]
            if len(lines) > 500:
                lines = lines[:500]
                lines.append(f"... (truncated, {len(result.split(chr(10))) - 500} more lines)")
            lines = [line[:200] + ('...' if len(line) > 200 else '') for line in lines]
            return '\n'.join(lines)
        except socket.timeout:
            return f"Error: Command timed out after {timeout}s"
        except (paramiko.SSHException, EOFError, socket.error, OSError) as e:
            # Connection might be broken, clear it so next call reconnects
            if self.ssh:
                try:
                    self.ssh.close()
                except Exception:
                    pass
                self.ssh = None
            return f"Error: SSH error - {type(e).__name__}: {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"
    
    def close(self) -> None:
        """Cleanup resources."""
        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
            self.ssh = None
        
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1
        
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


# Global session
_vm: Optional[VMSession] = None


def _run_vm_process(cmd: list[str], cwd: Optional[str]) -> tuple[subprocess.Popen, int]:
    """Start the VM process. Returns (process, master_fd)."""
    # Create a pseudo-terminal for the VM
    master_fd, slave_fd = pty.openpty()
    
    print(f"🚀 Starting VM with command: {' '.join(cmd)}")
    
    # Start the nixos-shell process
    process = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        cwd=cwd
    )
    
    # Close slave fd in parent process
    os.close(slave_fd)
    
    return process, master_fd   


def _wait_for_ssh(session: VMSession, timeout: float) -> bool:
    """Wait for SSH to become available."""
    start = time.time()

    print("Waiting for SSH.", end="", flush=True)
    while time.time() - start < timeout:
        if not session.is_running():
            return False
    
        if session.connect_ssh():
            session.booted = True
            print(" SSH ready", flush=True)
            return True
        print(".", end="", flush=True)
        time.sleep(2)
    
    return False


def _spawn_vm(flake_path: str = ".", boot_timeout: float = 300):
    """Spawn a nixos-shell VM for testing the packaged application."""
    global _vm
    
    if _vm and _vm.is_running():
        raise RuntimeError("Error: VM already running. Use shutdown_vm() first.")
    
    try:
        cmd = ["nixos-shell", "--flake", f"{flake_path}#vm"]
        cwd = os.path.abspath(flake_path) if flake_path != "." else None
        
        process, master_fd = _run_vm_process(cmd, cwd)
        session = VMSession(process, master_fd)
        _vm = session

        print(f"Process started with PID {process.pid}")
        
        # Wait for SSH to be available
        if not _wait_for_ssh(session, boot_timeout):
            # Read any output from the VM process to report errors
            vm_output = session.read_output()
            session.close()
            _vm = None
            error_msg = "Error: VM failed to boot (SSH not available) within timeout."
            if vm_output:
                error_msg += f"\n\nVM output:\n{vm_output}"
            return error_msg
        
        return "VM started successfully. Use run_in_vm() to execute commands."
        
    except FileNotFoundError:
        _vm = None
        raise RuntimeError("Error: nixos-shell not found.")
    except Exception as e:
        _vm = None
        raise RuntimeError(f"Error: {e}")


def _shutdown_vm() -> str:
    """Shutdown the VM."""
    global _vm
    
    if not _vm:
        return "No VM running."
    
    if not _vm.is_running():
       _vm.close()
       _vm = None
       return "VM already stopped."
    
    # Try graceful shutdown via SSH
    if _vm.ssh:
        try:
            _vm.ssh.exec_command("sudo poweroff", timeout=5)
            time.sleep(2)
        except Exception:
            pass
    
    # Force kill if still running
    if _vm.is_running():
        _vm.process.terminate()
        try:
            _vm.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _vm.process.kill()
    
    _vm.close()
    _vm = None
    return "VM shutdown."


def _get_vm_status() -> str:
    """Get VM status."""
    if not _vm:
        return "No VM session."
    if _vm.is_running():
        return "VM running" + (" (SSH ready)" if _vm.booted else " (booting)")
    return "VM stopped."


@log_function_call("run_in_vm")
def run_in_vm(command: str) -> str:
    """Execute a command in bash shell on a headless, isolated VM containing the package of interest in the system's global environment.
    Do not use Nix variables like $pkgs or $out, they are not defined in this context.
    The built package is available at /home/test/package (~/package) inside the VM.

    Arguments:
        command: The command to execute inside a bash shell.
    """
    if not _vm:
        return "Error: Unable to run command, no VM session found."
    
    if not _vm.is_running():
        return "Error: Unable to run command, no VM session found."
    
    return _vm.run_command(command, timeout=60)