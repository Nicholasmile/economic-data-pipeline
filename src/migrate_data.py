
from pathlib import Path
import shutil

# Project folder
project = Path(__file__).resolve().parent.parent

# Existing raw data folder
old_folder = project / "data" / "raw"

# New country-specific folder
new_folder = old_folder / "NGA" / "1990_2025"
new_folder.mkdir(parents=True, exist_ok=True)

# Existing filenames and new filenames
files = {
    "GDP_Growth.csv": "GDP_Growth_NY.GDP.MKTP.KD.ZG.csv",
    "nigeria_inflation_data.csv": "Inflation_FP.CPI.TOTL.ZG.csv",
    "Unemployment.csv": "Unemployment_SL.UEM.TOTL.ZS.csv"
}

# Copy existing datasets
for old_name, new_name in files.items():

    source = old_folder / old_name
    destination = new_folder / new_name

    if not source.exists():
        print(f"Missing source: {old_name}")
        continue

    if destination.exists():
        print(f"Already exists: {new_name}")
        continue

    shutil.copy2(source, destination)

    print(f"Copied: {old_name} -> {new_name}")

print("\nMigration completed!")