from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
import psycopg2
import requests
import os
import logging
from contextlib import contextmanager
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

RAILRADAR_API_KEY = os.getenv("RAILRADAR_API_KEY")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI()


app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)


# ============================================================
# GLOBAL ERROR HANDLING
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request",
            "detail": "Please check the request parameters."
        }
    )

@app.exception_handler(psycopg2.Error)
async def database_error_handler(request: Request, exc: psycopg2.Error):
    logger.exception(
        "Database error on %s %s",
        request.method,
        request.url.path
    )

    return JSONResponse(
        status_code=503,
       content={
        "error": "Database unavailable",
        "detail": "Database service is temporarily unavailable"
            }
    )

@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception(
        "Unexpected error on %s %s",
        request.method,
        request.url.path
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "Something went wrong on the server. Please try again later."
        }
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

@contextmanager
def get_db_cursor():
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
        cur = conn.cursor()
        yield cur

    except psycopg2.Error as exc:
        logger.error("Database error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database service is temporarily unavailable"
        )

    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    try:
        return FileResponse("frontend/index.html")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Frontend file is not available"
        )


# ============================================================
# TRAIN SEARCH
# ============================================================

@app.get("/trains/search")
def search_trains(q: str):
    q = q.strip()

    if not q:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT
                train_number,
                train_name
            FROM trains
            WHERE train_number ILIKE %s
               OR train_name ILIKE %s
            ORDER BY
                CASE
                    WHEN train_number = %s THEN 1
                    WHEN train_number ILIKE %s THEN 2
                    ELSE 3
                END,
                train_number
            LIMIT 10
            """,
            (
                f"%{q}%",
                f"%{q}%",
                q,
                f"{q}%"
            )
        )

        rows = cur.fetchall()

    return {
        "query": q,
        "count": len(rows),
        "results": [
            {
                "train_number": row[0],
                "train_name": row[1]
            }
            for row in rows
        ]
    }


# ============================================================
# TRAIN DETAILS
# ============================================================

@app.get("/trains/{train_number}")
def get_train(train_number: str):
    train_number = train_number.strip()

    if not train_number:
        raise HTTPException(
            status_code=400,
            detail="Train number cannot be empty"
        )

    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT
                t.train_number,
                t.train_name,
                s1.code,
                s1.name,
                s2.code,
                s2.name,
                t.runs_on
            FROM trains t
            JOIN stations s1
                ON t.source_station_id = s1.id
            JOIN stations s2
                ON t.destination_station_id = s2.id
            WHERE t.train_number = %s
            """,
            (train_number,)
        )

        train = cur.fetchone()

        if train is None:
            raise HTTPException(
                status_code=404,
                detail="Train not found"
            )

        cur.execute(
            """
            SELECT
                ts.sequence,
                s.code,
                s.name,
                ts.arrival_time,
                ts.departure_time,
                ts.halt_minutes,
                ts.distance_km,
                ts.day
            FROM train_stops ts
            JOIN stations s
                ON ts.station_id = s.id
            JOIN trains t
                ON ts.train_id = t.id
            WHERE t.train_number = %s
            ORDER BY ts.sequence
            """,
            (train_number,)
        )

        stops = cur.fetchall()

    return {
        "train_number": train[0],
        "train_name": train[1],
        "source": {
            "code": train[2],
            "name": train[3]
        },
        "destination": {
            "code": train[4],
            "name": train[5]
        },
        "runs_on": train[6],
        "stops": [
            {
                "sequence": row[0],
                "station_code": row[1],
                "station_name": row[2],
                "arrival": str(row[3]) if row[3] else None,
                "departure": str(row[4]) if row[4] else None,
                "halt_minutes": row[5],
                "distance_km": float(row[6]) if row[6] else None,
                "day": row[7]
            }
            for row in stops
        ]
    }


# ============================================================
# STATION SEARCH
# ============================================================

@app.get("/stations/search")
def search_stations(q: str):
    q = q.strip()

    if not q:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT code, name
            FROM stations
            WHERE code ILIKE %s
               OR name ILIKE %s
            ORDER BY name
            LIMIT 10
            """,
            (f"%{q}%", f"%{q}%")
        )

        rows = cur.fetchall()

    return {
        "results": [
            {
                "code": row[0],
                "name": row[1]
            }
            for row in rows
        ]
    }


# ============================================================
# STATION TRAINS
# ============================================================

@app.get("/stations/{station_code}/trains")
def get_station_trains(station_code: str):
    station_code = station_code.strip().upper()

    if not station_code:
        raise HTTPException(
            status_code=400,
            detail="Station code cannot be empty"
        )

    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT
                t.train_number,
                t.train_name,
                s.code,
                s.name,
                ts.arrival_time,
                ts.departure_time,
                ts.halt_minutes,
                ts.day
            FROM train_stops ts
            JOIN trains t
                ON ts.train_id = t.id
            JOIN stations s
                ON ts.station_id = s.id
            WHERE s.code = %s
            ORDER BY
                ts.day,
                ts.arrival_time,
                ts.departure_time
            """,
            (station_code,)
        )

        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Station not found or no trains found"
        )

    return {
        "station": {
            "code": rows[0][2],
            "name": rows[0][3]
        },
        "trains": [
            {
                "train_number": row[0],
                "train_name": row[1],
                "arrival": str(row[4]) if row[4] else None,
                "departure": str(row[5]) if row[5] else None,
                "halt_minutes": row[6],
                "day": row[7]
            }
            for row in rows
        ]
    }


# ============================================================
# RAILRADAR HELPER
# ============================================================

def railradar_headers():
    return {
        "Authorization": f"Bearer {RAILRADAR_API_KEY}"
    }


def parse_railradar_response(response, error_message):
    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail="RailRadar API key is invalid or expired"
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Railway data not found"
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="RailRadar API request limit reached"
        )

    if response.status_code == 503:
        raise HTTPException(
            status_code=503,
            detail="RailRadar service is temporarily unavailable"
        )

    if response.status_code != 200:
        logger.error(
            "RailRadar returned HTTP %s",
            response.status_code
        )
        raise HTTPException(
            status_code=502,
            detail="RailRadar API returned an error"
        )

    try:
        data = response.json()
    except ValueError:
        logger.error("RailRadar returned invalid JSON")
        raise HTTPException(
            status_code=502,
            detail="RailRadar returned an invalid response"
        )

    if not isinstance(data, dict):
        logger.error("RailRadar returned an unexpected response format")
        raise HTTPException(
            status_code=502,
            detail="RailRadar returned an unexpected response"
        )

    if not data.get("success"):
        raise HTTPException(
            status_code=502,
            detail=error_message
        )

    return data


# ============================================================
# LIVE TRAIN STATUS - RAILRADAR
# ============================================================

@app.get("/trains/{train_number}/live")
def get_live_train(train_number: str):
    if not RAILRADAR_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="RailRadar API key is not configured"
        )

    train_number = train_number.strip()

    if not train_number:
        raise HTTPException(
            status_code=400,
            detail="Train number cannot be empty"
        )

    url = (
        f"https://api.railradar.in/"
        f"v1/trains/{train_number}/live"
    )

    try:
        response = requests.get(
            url,
            headers=railradar_headers(),
            timeout=30
        )
    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="RailRadar request timed out"
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RailRadar"
        )

    return parse_railradar_response(
        response,
        "RailRadar could not provide live data"
    )


# ============================================================
# LIVE STATION BOARD - RAILRADAR
# ============================================================

@app.get("/stations/{station_code}/live")
def get_live_station(station_code: str):
    if not RAILRADAR_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="RailRadar API key is not configured"
        )

    station_code = station_code.strip().upper()

    if not station_code:
        raise HTTPException(
            status_code=400,
            detail="Station code cannot be empty"
        )

    url = f"https://api.railradar.in/v1/stations/{station_code}/live"

    try:
        response = requests.get(
            url,
            headers=railradar_headers(),
            params={"hours": 4},
            timeout=30
        )
    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="RailRadar request timed out"
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RailRadar"
        )

    return parse_railradar_response(
        response,
        "RailRadar could not provide live station data"
    )
