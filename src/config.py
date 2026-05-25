from pathlib import Path
from datetime import date

LAT = 47.5999
LON = 19.0616
LOCATION_LABEL = "1039 Budapest, Sarkadi Imre utca 6"

START_DATE = "2020-01-01"
END_DATE = date.today().isoformat()          # update to a fixed date if needed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = DATA_DIR / "environmental_data.csv"
OUTPUT_REPORT = DATA_DIR / "data_quality_report.txt"
