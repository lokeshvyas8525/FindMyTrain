# FindMyTrain

FindMyTrain is a railway information web application that helps users search for trains, view train routes and schedules, check live train running status, and find trains at a particular railway station.

## Features

- Search trains by train number or train name
- View complete train details and route
- View scheduled train timings at a particular station
- Check live train running status
- View current train location and delay
- View previous and next halt information
- View expected arrival and departure information
- View live station arrival and departure information
- Responsive web interface
- Automated backend testing

## Tech Stack

### Frontend
- HTML
- CSS
- JavaScript

### Backend
- Python
- FastAPI

### Database
- PostgreSQL

### External API
- RailRadar API

### Railway Data
- Railpull / NTES-based railway timetable data

## Project Architecture

```text
                    +----------------+
                    |      User      |
                    +-------+--------+
                            |
                            v
                  +-------------------+
                  | Frontend          |
                  | HTML/CSS/JS       |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | FastAPI Backend   |
                  +----+----------+---+
                       |          |
                       v          v
                +----------+  +-------------+
                |PostgreSQL|  | RailRadar   |
                | Database |  | API         |
                +----------+  +-------------+
                