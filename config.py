# ECONOMIC RESEARCH DATA PIPELINE
# Central Configuration File

# Country  settings
COUNTRY = "NGA"
COUNTRY_NAME = "Nigeria"

# Research period
START_YEAR = 1990
END_YEAR = 2025

# Economic indicators
INDICATORS = {
    "GDP_Growth": "NY.GDP.MKTP.KD.ZG",
    "Inflation": "FP.CPI.TOTL.ZG",
    "Unemployment": "SL.UEM.TOTL.ZS",
    "FDI": "BX.KLT.DINV.WD.GD.ZS"
}

# Data storage folders
RAW_DATA_FOLDER = "data/raw"
PROCESSED_DATA_FOLDER = "data/processed"