
import sys
from pathlib import Path

import pandas as pd
import requests

# Allow Python to find config.py
project_folder = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_folder))

from config import (
    COUNTRY,
    START_YEAR,
    END_YEAR,
    INDICATORS,
    RAW_DATA_FOLDER
)

# Create a folder specific to the research settings
output_folder = (
    project_folder
    / RAW_DATA_FOLDER
    / COUNTRY
    / f"{START_YEAR}_{END_YEAR}"
)

output_folder.mkdir(parents=True, exist_ok=True)

# Download each economic indicator
for name, code in INDICATORS.items():

    file_path = output_folder / f"{name}_{code}.csv"

    # Reuse existing downloads
    if file_path.exists():
        print(f"{name}: Cached file found. Skipping.")
        continue

    print(f"Downloading {name}...")

    url = (
        f"https://api.worldbank.org/v2/"
        f"country/{COUNTRY}/indicator/{code}"
    )

    try:
        response = requests.get(
            url,
            params={
                "format": "json",
                "date": f"{START_YEAR}:{END_YEAR}",
                "per_page": 100
            },
            timeout=20
        )

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            print(f"{name}: No data returned.")
            continue

        df = pd.DataFrame(data[1])

        df = df[["date", "value"]]
        df.columns = ["Year", name]

        df["Year"] = df["Year"].astype(int)
        df = df.sort_values("Year")

        df.to_csv(file_path, index=False)

        print(f"{name}: {len(df)} records saved.")

    except requests.exceptions.RequestException as error:
        print(f"{name}: Connection failed - {error}")

    except (ValueError, KeyError, TypeError) as error:
        print(f"{name}: Processing failed - {error}")

print("\nExtraction stage completed!")
