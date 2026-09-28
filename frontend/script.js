const trainSearch = document.getElementById("trainSearch");
const searchButton = document.getElementById("searchButton");
const results = document.getElementById("results");

const stationSearch = document.getElementById("stationSearch");
const stationSearchButton = document.getElementById("stationSearchButton");
const stationResults = document.getElementById("stationResults");

const esc = (value) =>
    String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

const msg = (el, text) => {
    el.innerHTML = `<div class="message">${esc(text)}</div>`;
};

const time = (value) => {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit"
    });
};

const dateTime = (value) => {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit"
    });
};

const delayText = (value) => {
    if (value == null) return "-";
    if (value < 0) return `${Math.abs(value)} min early`;
    if (value === 0) return "On time";
    return `${value} min late`;
};

const delayClass = (value) => {
    if (value < 0) return "early";
    if (value > 0) return "late";
    return "ontime";
};

const statusBadge = (status) => {
    const s = String(status || "scheduled").toLowerCase();
    const label = s.replace(/-/g, " ");
    return `<span class="badge ${esc(s)}">${esc(label)}</span>`;
};

searchButton.onclick = searchTrain;
trainSearch.onkeydown = (e) => {
    if (e.key === "Enter") searchTrain();
};

stationSearchButton.onclick = searchStation;
stationSearch.onkeydown = (e) => {
    if (e.key === "Enter") searchStation();
};

async function searchTrain() {
    const q = trainSearch.value.trim();

    if (!q) {
        msg(results, "Please enter a train number or train name.");
        return;
    }

    msg(results, "Searching trains...");

    try {
        const response = await fetch(`/trains/search?q=${encodeURIComponent(q)}`);
        const data = await response.json();

        if (!response.ok) {
            msg(results, data.detail || "Search failed.");
            return;
        }

        if (!data.results.length) {
            msg(results, "No train found.");
            return;
        }

        results.innerHTML = data.results.map((train) => `
            <div class="item">
                <h3>${esc(train.train_number)}</h3>
                <p>${esc(train.train_name)}</p>
                <div class="actions">
                    <button class="primary" onclick="showTrainDetails('${esc(train.train_number)}')">
                        View Details
                    </button>
                    <button class="secondary" onclick="showLiveStatus('${esc(train.train_number)}')">
                        Live Status
                    </button>
                </div>
            </div>
        `).join("");
    } catch (error) {
        msg(results, "Unable to connect to backend.");
        console.error(error);
    }
}

async function showTrainDetails(number) {
    msg(results, "Loading train details...");

    try {
        const response = await fetch(`/trains/${encodeURIComponent(number)}`);
        const train = await response.json();

        if (!response.ok) {
            msg(results, train.detail || "Train not found.");
            return;
        }

        const rows = train.stops.map((stop) => `
            <tr>
                <td>${esc(stop.sequence)}</td>
                <td><b>${esc(stop.station_code)}</b><br>${esc(stop.station_name)}</td>
                <td>${esc(stop.arrival || "-")}</td>
                <td>${esc(stop.departure || "-")}</td>
                <td>${esc(stop.halt_minutes ?? "-")} min</td>
                <td>${esc(stop.distance_km ?? "-")} km</td>
                <td>Day ${esc(stop.day)}</td>
            </tr>
        `).join("");

        results.innerHTML = `
            <div class="panel">
                <button class="back" onclick="searchTrain()">← Back to Results</button>

                <h2>${esc(train.train_number)} — ${esc(train.train_name)}</h2>

                <div class="grid">
                    <div class="info">
                        <span class="label">From</span>
                        <span class="value">${esc(train.source.name)} (${esc(train.source.code)})</span>
                    </div>
                    <div class="info">
                        <span class="label">To</span>
                        <span class="value">${esc(train.destination.name)} (${esc(train.destination.code)})</span>
                    </div>
                    <div class="info">
                        <span class="label">Runs On</span>
                        <span class="value">${esc(train.runs_on)}</span>
                    </div>
                </div>

                <button class="success" onclick="showLiveStatus('${esc(train.train_number)}')">
                    View Live Status
                </button>

                <h3>Train Route</h3>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Station</th>
                                <th>Arrival</th>
                                <th>Departure</th>
                                <th>Halt</th>
                                <th>Distance</th>
                                <th>Day</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        msg(results, "Unable to load train details.");
        console.error(error);
    }
}

async function showLiveStatus(number) {
    msg(results, "Loading live train status...");

    try {
        const response = await fetch(`/trains/${encodeURIComponent(number)}/live`);
        const payload = await response.json();

        if (!response.ok) {
            msg(results, payload.detail || "Unable to load live status.");
            return;
        }

        const data = payload.data;
        const train = data.train;
        const current = data.currentLocation || {};
        const next = data.nextHalt || {};
        const previous = data.previousHalt || {};

        const currentRoute = (data.route || []).find(
            (item) => item.sequence === current.sequence
        );

        const rows = (data.route || []).map((station) => `
            <tr class="${station.sequence === current.sequence ? "current" : ""}">
                <td>${esc(station.sequence)}</td>
                <td><b>${esc(station.stationCode)}</b><br>${esc(station.stationName)}</td>
                <td>${time(station.scheduledArrival)}</td>
                <td>${time(station.scheduledDeparture)}</td>
                <td>${esc(station.status || "-")}</td>
                <td>${esc(station.platform || "-")}</td>
                <td>${esc(station.delayArrival ?? station.delayDeparture ?? "-")}</td>
                <td>${esc(station.distance ?? "-")} km</td>
            </tr>
        `).join("");

        results.innerHTML = `
            <div class="panel">
                <button class="back" onclick="searchTrain()">← Back to Results</button>

                <h2>${esc(train.number)} — ${esc(train.name)}</h2>
                <p>${esc(train.source.name)} (${esc(train.source.code)})
                → ${esc(train.destination.name)} (${esc(train.destination.code)})</p>

                <div class="live-box">
                    <div class="live-title">
                        <h3>Live Status</h3>
                        <span class="live-pill">Live</span>
                    </div>

                    <div class="grid">
                        <div class="info">
                            <span class="label">Status</span>
                            <span class="value">${esc(data.status || "-")}</span>
                        </div>
                        <div class="info">
                            <span class="label">Current Location</span>
                            <span class="value">${esc(current.stationName || "-")} (${esc(current.stationCode || "-")})</span>
                        </div>
                        <div class="info">
                            <span class="label">Delay</span>
                            <span class="value ${delayClass(data.delayMinutes)}">${esc(delayText(data.delayMinutes))}</span>
                        </div>
                        <div class="info">
                            <span class="label">Previous Halt</span>
                            <span class="value">${esc(previous.stationName || "-")} (${esc(previous.stationCode || "-")})</span>
                        </div>
                        <div class="info">
                            <span class="label">Next Halt</span>
                            <span class="value">${esc(next.stationName || "-")} (${esc(next.stationCode || "-")})</span>
                        </div>
                        <div class="info">
                            <span class="label">Distance From Origin</span>
                            <span class="value">${esc(current.distanceFromOriginKm ?? "-")} km</span>
                        </div>
                        <div class="info">
                            <span class="label">Platform</span>
                            <span class="value">${esc(currentRoute?.platform || "-")}</span>
                        </div>
                        <div class="info">
                            <span class="label">Speed To Next</span>
                            <span class="value">${esc(currentRoute?.speedToNextStationKmph ?? "-")} km/h</span>
                        </div>
                        <div class="info">
                            <span class="label">Last Updated</span>
                            <span class="value">${esc(dateTime(data.lastUpdatedAt))}</span>
                        </div>
                    </div>
                </div>

                <h3>Live Route</h3>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Station</th>
                                <th>Arrival</th>
                                <th>Departure</th>
                                <th>Status</th>
                                <th>Platform</th>
                                <th>Delay</th>
                                <th>Distance</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        msg(results, "Unable to connect to live train service.");
        console.error(error);
    }
}

async function searchStation() {
    const q = stationSearch.value.trim();

    if (!q) {
        msg(stationResults, "Please enter a station name or code.");
        return;
    }

    msg(stationResults, "Searching stations...");

    try {
        const response = await fetch(`/stations/search?q=${encodeURIComponent(q)}`);
        const data = await response.json();

        if (!response.ok) {
            msg(stationResults, data.detail || "Station search failed.");
            return;
        }

        if (!data.results.length) {
            msg(stationResults, "No station found.");
            return;
        }

        stationResults.innerHTML = data.results.map((station) => `
            <div class="item">
                <h3>${esc(station.name)}</h3>
                <p>Station Code: <b>${esc(station.code)}</b></p>
                <div class="actions">
                    <button class="primary" onclick="showStationTrains('${esc(station.code)}')">
                        Scheduled Trains
                    </button>
                    <button class="success" onclick="showLiveStation('${esc(station.code)}')">
                        Live Board
                    </button>
                </div>
            </div>
        `).join("");
    } catch (error) {
        msg(stationResults, "Unable to connect to backend.");
        console.error(error);
    }
}

async function showStationTrains(code) {
    msg(stationResults, "Loading scheduled trains...");

    try {
        const response = await fetch(`/stations/${encodeURIComponent(code)}/trains`);
        const data = await response.json();

        if (!response.ok) {
            msg(stationResults, data.detail || "Unable to load station trains.");
            return;
        }

        const rows = data.trains.map((train) => `
            <tr>
                <td><b>${esc(train.train_number)}</b></td>
                <td>${esc(train.train_name)}</td>
                <td>${esc(train.arrival || "-")}</td>
                <td>${esc(train.departure || "-")}</td>
                <td>${esc(train.halt_minutes ?? "-")} min</td>
                <td>Day ${esc(train.day)}</td>
            </tr>
        `).join("");

        stationResults.innerHTML = `
            <div class="panel">
                <button class="back" onclick="searchStation()">← Back to Stations</button>
                <h2>${esc(data.station.name)} (${esc(data.station.code)})</h2>
                <p>Scheduled trains stopping at this station.</p>

                <div class="actions">
                    <button class="success" onclick="showLiveStation('${esc(data.station.code)}')">
                        View Live Board
                    </button>
                </div>

                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Train Number</th>
                                <th>Train Name</th>
                                <th>Arrival</th>
                                <th>Departure</th>
                                <th>Halt</th>
                                <th>Day</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        msg(stationResults, "Unable to load station trains.");
        console.error(error);
    }
}

async function showLiveStation(code) {
    msg(stationResults, "Loading live station board...");

    try {
        const response = await fetch(`/stations/${encodeURIComponent(code)}/live`);
        const payload = await response.json();

        if (!response.ok) {
            msg(stationResults, payload.detail || "Unable to load live station board.");
            return;
        }

        const data = payload.data;
        const station = data.station;
        const windowData = data.window || {};

        const rows = (data.trains || []).map((item) => {
            const live = item.live || {};
            const stop = item.stop || {};
            const train = item.train || {};

            return `
                <div class="board-row">
                    <div>
                        <div class="train-number">${esc(train.number || "-")}</div>
                        <div class="small">${esc(train.type || "")}</div>
                    </div>
                    <div class="train-name">${esc(train.name || "-")}</div>
                    <div>
                        <div><b>${esc(time(live.expectedArrivalTime))}</b></div>
                        <div class="small">Arrives</div>
                    </div>
                    <div>
                        <div><b>${esc(time(live.expectedDepartureTime))}</b></div>
                        <div class="small">Departs</div>
                    </div>
                    <div>${esc(live.platform || stop.platform || "-")}</div>
                    <div>
                        ${statusBadge(live.type)}
                        <div class="${delayClass(live.delayMinutes)} small">
                            ${esc(delayText(live.delayMinutes))}
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        stationResults.innerHTML = `
            <div class="panel">
                <button class="back" onclick="searchStation()">← Back to Stations</button>

                <div class="live-title">
                    <div>
                        <h2>${esc(station.name)} (${esc(station.code)})</h2>
                        <p>Live arrival & departure board</p>
                    </div>
                    <span class="live-pill">Live</span>
                </div>

                <div class="station-board">
                    <div class="board-head">
                        <div>
                            <h3>Upcoming Trains</h3>
                            <p>
                                Window: ${esc(windowData.from || "-")} → ${esc(windowData.to || "-")}
                            </p>
                        </div>
                        <div class="small">${esc(data.trains?.length || 0)} trains</div>
                    </div>

                    <div class="train-board">
                        <div class="board-row header">
                            <div>Number</div>
                            <div>Train</div>
                            <div>Arrival</div>
                            <div>Departure</div>
                            <div>Platform</div>
                            <div>Status</div>
                        </div>

                        ${rows || '<div class="message">No live trains found for this station.</div>'}
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        msg(stationResults, "Unable to connect to live station service.");
        console.error(error);
    }
}
