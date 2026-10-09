
import sys
from pathlib import Path
import pandas as pd

# Locate the project folder
project = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project))

# Import research settings
from config import (
    COUNTRY,
    START_YEAR,
    END_YEAR,
    INDICATORS,
    RAW_DATA_FOLDER,
    PROCESSED_DATA_FOLDER
)

# Input and output folders
raw_folder = (
    project
    / RAW_DATA_FOLDER
    / COUNTRY
    / f"{START_YEAR}_{END_YEAR}"
)

processed_folder = (
    project
    / PROCESSED_DATA_FOLDER
    / COUNTRY
    / f"{START_YEAR}_{END_YEAR}"
)

processed_folder.mkdir(parents=True, exist_ok=True)

# Create a complete year column
df_merged = pd.DataFrame({
    "Year": range(START_YEAR, END_YEAR + 1)
})

# Merge each available indicator
for name, code in INDICATORS.items():

    file_path = raw_folder / f"{name}_{code}.csv"

    if not file_path.exists():
        print(f"{name}: File missing. Skipping.")
        continue

    df = pd.read_csv(file_path)

    df_merged = df_merged.merge(
        df[["Year", name]],
        on="Year",
        how="left"
    )

    print(f"{name}: Merged successfully.")

# Save the combined dataset
output_file = (
    processed_folder
    / f"{COUNTRY}_economic_data.csv"
)

df_merged.to_csv(output_file, index=False)

print("\nMerged dataset preview:")
print(df_merged.head())

print("\nMissing values:")
print(df_merged.isnull().sum())

print(f"\nDataset saved to: {output_file}")