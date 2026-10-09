import requests
import pandas as pd

# Research settings
country = "NGA"  # Nigeria
indicator = "FP.CPI.TOTL.ZG"  # Inflation, consumer prices (annual %)

# World Bank API URL
url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"

# Retrieve data from the World Bank API
response = requests.get(
    url,
    params={"format": "json", "per_page": 1000},
    timeout=30
)

response.raise_for_status()  # Raise an error for bad responses

# Convert JSON response to DataFrame
data = response.json()  # The second element contains the data
df = pd.DataFrame(data[1])

# Select relevant columns
df = df[["date", "value"]]

# Rename columns for clarity
df.columns = ["Year", "Inflation"]

# save data
df.to_csv("data/raw/nigeria_inflation_data.csv", index=False)

print(df.head())
print("Inflation data saved successfully")