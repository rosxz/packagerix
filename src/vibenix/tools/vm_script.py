"""VM testing tool using nixos-shell with script execution via shared folder."""

import logging
import pty
import subprocess
import os
import time
from pathlib import Path
from typing import Optional

from vibenix.ccl_log import log_function_call

logging.getLogger("paramiko").setLevel(logging.CRITICAL)
logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL)


def _run_script_in_vm(script: str, system_packages: str, flake_path: str = ".", timeout: float = 30) -> str:
    """Run a shell script in a VM that starts, executes the script, and shuts down.

    Args:
        script: Shell script content (without shebang line)
        system_packages: Nix expression for systemPackages (e.g., "[ pkg ]" or "[ pkg (pkgs.python3.withPackages (ps: [ pkg ])) ]")
        flake_path: Path to the flake directory
        timeout: Maximum time to wait for VM to complete (seconds)

    Returns:
        The output from the script execution
    """
    # Create task directory in the working directory
    flake_path_obj = Path(flake_path).resolve()
    task_dir = flake_path_obj / "vm-task"
    task_dir.mkdir(parents=True, exist_ok=True)

    # Write the script and output to the task directory
    script_file = task_dir / "run.sh"
    output_file = task_dir / "output.txt"

    # Write packages.nix directly in the flake directory (not in task dir)
    packages_file = flake_path_obj / "packages.nix"

    # Clean up any previous output and VM state
    if output_file.exists():
        output_file.unlink()

    # Clean up any previous qcow2 VM disk image to ensure fresh state
    qcow2_file = flake_path_obj / "nixos.qcow2"
    if qcow2_file.exists():
        qcow2_file.unlink()

    # Always write system packages configuration (even if default)
    packages_file.write_text(system_packages)

    # Write script with proper permissions
    script_file.write_text(script)
    script_file.chmod(0o755)

    print(f"🚀 Starting VM to execute script")

    # Create a pseudo-terminal for the VM
    master_fd, slave_fd = pty.openpty()

    # Start the nixos-shell process
    cmd = ["nixos-shell", "--flake", f"{flake_path}#vm-script"]
    process = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        cwd=flake_path
    )

    # Close slave fd in parent process
    os.close(slave_fd)

    print(f"Process started with PID {process.pid}")

    # Wait for the VM to complete (it will shutdown automatically)
    # Collect VM console output for debugging
    import select
    vm_output = []
    start_time = time.time()

    while process.poll() is None:
        if time.time() - start_time > timeout:
            print(f"⏱️  VM execution timed out after {timeout}s, terminating...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            os.close(master_fd)
            return f"Error: VM execution timed out after {timeout}s"

        # Read any available output
        readable, _, _ = select.select([master_fd], [], [], 0.1)
        if readable:
            try:
                data = os.read(master_fd, 4096)
                if data:
                    vm_output.append(data.decode('utf-8', errors='replace'))
            except OSError:
                pass

        time.sleep(0.1)

    # Close the PTY
    os.close(master_fd)

    vm_console = ''.join(vm_output)

    print(f"VM exited with code {process.returncode}")

    # Check if output file was created
    if not output_file.exists():
        print(f"Output file not found at {output_file}")
        print(f"Task directory contents: {list(task_dir.iterdir())}")
        print(f"VM console output (last 2000 chars):\n{vm_console[-2000:]}")
        return f"Error: VM did not produce output file\n\nVM console output:\n{vm_console[-1000:]}"

    # Read and return the output
    try:
        output = output_file.read_text()

        # Limit output similar to the SSH version
        lines = output.split('\n')
        if len(lines) > 500:
            lines = lines[:500]
            lines.append(f"... (truncated, {len(output.split(chr(10))) - 500} more lines)")
        lines = [line[:200] + ('...' if len(line) > 200 else '') for line in lines]

        return '\n'.join(lines).rstrip()
    except Exception as e:
        return f"Error reading output: {e}"


@log_function_call("run_in_vm")
def run_in_vm(*, script: str, system_packages: str = "[ pkg ]") -> str:
    """Execute a shell script in a headless, isolated VM containing the package of interest.

    The VM will start up, execute your script, write output to a file, and shut down automatically.
    The script runs as the 'test' user in the VM. The built package is available at /home/test/package.

    Arguments:
        script: Shell script content to execute (without #!/bin/sh shebang line).
                The script will be executed with /bin/sh and output captured automatically.
        system_packages: Nix list expression for environment.systemPackages (default: "[ pkg ]").
                         The variables 'pkg' (the built package) and 'pkgs' (nixpkgs) are automatically in scope.
                         Examples:
                         - "[ pkg ]" - Just the package itself (default)
                         - "[ pkg (pkgs.python3.withPackages (ps: [ pkg ])) ]" - Package + Python environment

    Returns:
        The stdout and stderr output from the script execution.
    """
    from vibenix import config

    try:
        return _run_script_in_vm(script, system_packages, str(config.flake_dir))
    except FileNotFoundError:
        return "Error: nixos-shell not found. Please ensure nixos-shell is installed."
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
