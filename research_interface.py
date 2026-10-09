
from pathlib import Path
import pandas as pd

# Economic Research Data Platform
print("=" * 45)
print("ECONOMIC RESEARCH DATA PLATFORM")
print("=" * 45)

# Researcher inputs
country = input("Enter country code (e.g. NGA): ").strip().upper()
start_year = int(input("Enter start year: "))
end_year = int(input("Enter end year: "))

# Display research settings
print("\nYOUR RESEARCH SETTINGS")
print("-" * 45)

print("Country:", country)
print("Start Year:", start_year)
print("End Year:", end_year)

# Validate research settings
if not country:
    print("\nError: Country code cannot be empty.")

elif start_year > end_year:
    print("\nError: Start year cannot exceed end year.")

else:
    print("\nResearch settings accepted!")

    # Find the project folder
    project = Path(__file__).resolve().parent

    # Locate the requested dataset
    dataset = (
        project
        / "data"
        / "processed"
        / country
        / f"{start_year}_{end_year}"
        / f"{country}_economic_data.csv"
    )

    # Check whether the dataset exists

if dataset.exists():
    print("\nDataset found!")
    print("Location:", dataset)

    # Load the economic dataset
    df = pd.read_csv(dataset)

    # Display the first five observations
    print("\nDATASET PREVIEW")
    print("-" * 45)
    print(df.head())

    # Display dataset information
    print("\nDATASET INFORMATION")
    print("Total observations:", len(df))
    print("Available indicators:", list(df.columns[1:]))

    # Display missing observations
    print("\nMISSING VALUES")
    print(df.isnull().sum())

    # show available indicators
    indicators = list(df.columns[1:])

    print("\nSELECT ECONOMIC INDICATORS")

    for number, indicator in enumerate(indicators, start=1):
        print(f"{number}. {indicator}")

    # Ask the researcher to select indicators
    selection = input(
        "\nEnter indicators numbers separated by commas (e.g 1,2): "
    )

    # Convert selections to indicator names
    try:
        numbers = [int(item.strip()) for item in selection.split(",")]

        if not numbers or any(
            number < 1 or number > len(indicators)
            for number in numbers
        ):
            raise ValueError
        selected_indicators =[
            indicators[number - 1]
            for number in numbers
        ]

        # Always retain the Year column
        selected_columns = ["Year"] + list(
            dict.fromkeys(selected_indicators)
        )

        df = df[selected_columns]

        print("\nSELECTED DATASET")
        print(df.head())

    except ValueError:
        print("\nInvalid selection. Keeping all indicators")

    # Ask whether the researcher wants an Excel file
    export = input("\nExport dataset to Excel? (yes/no): ").strip().lower()

    if export == "yes":
        indicator_names = "_".join(df.columns[1:])

        excel_file = (
            dataset.parent
            / f"{country}_{start_year}_{end_year}_{indicator_names}.xlsx"
        )
        df.to_excel(excel_file, index=False)
        print("Dataset exported to:", excel_file)

    else:
        print("Excel export skipped.")

else:
    print("\nDataset not found.")
    print("The requested dataset has not been generated yet.")
