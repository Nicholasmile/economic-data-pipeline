
import sys
from pathlib import Path
import pandas as pd

# Locate project folder
project = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project))

# Import configuration
from config import (
    COUNTRY,
    START_YEAR,
    END_YEAR,
    PROCESSED_DATA_FOLDER
)

# Locate the processed dataset
data_folder = (
    project
    / PROCESSED_DATA_FOLDER
    / COUNTRY
    / f"{START_YEAR}_{END_YEAR}"
)

file_path = data_folder / f"{COUNTRY}_economic_data.csv"

# Check that the dataset exists
if not file_path.exists():
    raise FileNotFoundError(
        f"Dataset not found: {file_path}"
    )

# Load dataset
df = pd.read_csv(file_path)

print("\nECONOMIC DATA QUALITY REPORT")
print("=" * 40)

# Dataset information
print("\nDataset shape:", df.shape)
print("Year range:", df["Year"].min(), "-", df["Year"].max())

# Check duplicate years
duplicates = df["Year"].duplicated().sum()
print("Duplicate years:", duplicates)

# Check missing values
missing_values = df.isnull().sum()

print("\nMISSING VALUES")
print(missing_values)

# Calculate missing percentages
missing_percentage = df.isnull().mean() * 100

print("\nMISSING VALUE PERCENTAGES")
print(missing_percentage.round(2))

# Count available observations
available = df.count()

print("\nAVAILABLE OBSERVATIONS")
print(available)

# Create quality report
report = pd.DataFrame({
    "Missing_Values": missing_values,
    "Missing_Percentage": missing_percentage.round(2),
    "Available_Observations": available
})

# Save report
report_file = data_folder / "data_quality_report.csv"
report.to_csv(report_file, index_label="Variable")

print(f"\nQuality report saved to: {report_file}")