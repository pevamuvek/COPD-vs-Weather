"""Export daily Kp summaries independently from the core environmental pipeline."""

from config import END_DATE, OUTPUT_KP_CSV, START_DATE
from fetchers import fetch_kp_index


def main():
    kp = fetch_kp_index(START_DATE, END_DATE)
    if kp.empty or kp["Kp_n"].sum() == 0:
        raise RuntimeError("No valid Kp readings were returned; no CSV was written.")

    kp.index.name = "date"
    kp.to_csv(OUTPUT_KP_CSV)
    print(f"Kp data saved -> {OUTPUT_KP_CSV} ({len(kp)} days)")
    return kp


if __name__ == "__main__":
    main()
