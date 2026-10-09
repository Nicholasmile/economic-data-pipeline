import subprocess
import sys
from pathlib import Path

# Find the project directory
project_folder = Path(__file__).resolve().parent

# Pipeline stages 
scripts = [
    "merge_indicators.py",
    "validate_data.py"
]

print("STARTING ECONOMIC DATA PIPELINE")
print("=" * 40)

for script in scripts:

    print(f"\nRunning {script}...", flush=True)

    script_path = project_folder / "src" / script

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_folder 
    )

    if result.returncode != 0:
        print(f"Pipeline stopped: {script} failed.")
        sys.exit(1)

print("\nECONOMIC DATA PIPELINE COMPLETED")