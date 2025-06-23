import subprocess
import os
import sys

def main():
    """
    Launches the Streamlit web application.

    This script runs the Streamlit app with the --server.fileWatcherType=none flag.
    This is a workaround for a known issue on some systems (especially macOS)
    where Streamlit's file watcher conflicts with the torch library,
    causing a RuntimeError.

    Disabling the file watcher means you will need to manually stop and
    restart the server to see changes in the source code.
    """
    # Ensure the script is run from the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_root, "interfaces", "app.py")

    if not os.path.exists(app_path):
        print(f"Error: Could not find the application file at {app_path}")
        sys.exit(1)

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.fileWatcherType",
        "none"
    ]

    print(f"Running command: {' '.join(command)}")

    try:
        # Using subprocess.run to execute the command
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print(f"Error: Python executable not found at '{sys.executable}'.")
        print("Please ensure your Python environment is correctly configured.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running the Streamlit app: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStreamlit server stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main() 