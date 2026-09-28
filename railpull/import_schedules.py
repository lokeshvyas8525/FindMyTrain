import json
import sys
from pathlib import Path
from datetime import time
from decimal import Decimal, InvalidOperation
from getpass import getpass

import psycopg2


DB_CONFIG = {
    "host": "localhost",
    "database": "find_my_train",
    "user": "postgres",
}


def parse_time(value):
    if not value:
        return None

    value = str(value).strip()

    if ":" not in value:
        return None

    try:
        hour, minute = map(int, value.split(":")[:2])
        hour = hour % 24
        return time(hour, minute)
    except:
        return None


def parse_int(value):
    try:
        return int(float(str(value).strip()))
    except:
        return None


def parse_decimal(value):
    if value is None or str(value).strip() == "":
        return None

    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def get_station_id(cur, code, name):

    code = str(code or "").strip()
    name = str(name or "").strip()

    if not code:
        return None

    cur.execute(
        """
        INSERT INTO stations (code, name)
        VALUES (%s, %s)
        ON CONFLICT (code)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (code, name)
    )

    return cur.fetchone()[0]


def import_file(cur, file_path):

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    train_number = str(data.get("TrainNumber", "")).strip()

    if not train_number:
        raise ValueError("TrainNumber missing")

    train_name = str(
        data.get("TrainName")
        or data.get("TrainTypeDesc")
        or "Unknown Train"
    ).strip()

    runs_on = str(data.get("DaysOfRun") or "").strip()

    stations_data = data.get("stations", [])

    if not stations_data:
        raise ValueError("No stations found")

    source = stations_data[0]
    destination = stations_data[-1]

    source_id = get_station_id(
        cur,
        source.get("StationCode"),
        source.get("StationName")
    )

    destination_id = get_station_id(
        cur,
        destination.get("StationCode"),
        destination.get("StationName")
    )

    cur.execute(
        """
        INSERT INTO trains
        (
            train_number,
            train_name,
            source_station_id,
            destination_station_id,
            runs_on
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (train_number)
        DO UPDATE SET
            train_name = EXCLUDED.train_name,
            source_station_id = EXCLUDED.source_station_id,
            destination_station_id = EXCLUDED.destination_station_id,
            runs_on = EXCLUDED.runs_on
        RETURNING id
        """,
        (
            train_number,
            train_name,
            source_id,
            destination_id,
            runs_on
        )
    )

    train_id = cur.fetchone()[0]

    # Re-import par duplicate stops na bane
    cur.execute(
        "DELETE FROM train_stops WHERE train_id = %s",
        (train_id,)
    )

    stops = 0

    for index, station in enumerate(stations_data, start=1):

        station_id = get_station_id(
            cur,
            station.get("StationCode"),
            station.get("StationName")
        )

        if station_id is None:
            continue

        sequence = parse_int(station.get("Sr")) or index
        day = parse_int(station.get("Day")) or 1

        cur.execute(
            """
            INSERT INTO train_stops
            (
                train_id,
                station_id,
                sequence,
                arrival_time,
                departure_time,
                halt_minutes,
                distance_km,
                day
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                train_id,
                station_id,
                sequence,
                parse_time(station.get("STA")),
                parse_time(station.get("STD")),
                parse_int(station.get("Halt")),
                parse_decimal(station.get("Distance")),
                day
            )
        )

        stops += 1

    return train_number, stops


def main():

    schedule_dir = Path("data/raw/schedules")

    files = list(schedule_dir.glob("*.json"))

    if not files:
        print("No JSON schedule files found.")
        return

    print(f"Found {len(files)} JSON files.")

    password = getpass("PostgreSQL password: ")

    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=password
    )

    success = 0
    failed = 0
    total_stops = 0

    try:

        with conn.cursor() as cur:

            for i, file_path in enumerate(files, start=1):

                try:

                    train_number, stops = import_file(
                        cur,
                        file_path
                    )

                    conn.commit()

                    success += 1
                    total_stops += stops

                    print(
                        f"[{i}/{len(files)}] "
                        f"{train_number} -> {stops} stops"
                    )

                except Exception as e:

                    conn.rollback()
                    failed += 1

                    print(
                        f"[{i}/{len(files)}] "
                        f"FAILED {file_path.name}: {e}"
                    )

        print()
        print("========== IMPORT COMPLETE ==========")
        print("Files found   :", len(files))
        print("Imported      :", success)
        print("Failed        :", failed)
        print("Total stops   :", total_stops)

    finally:
        conn.close()


if __name__ == "__main__":
    main()