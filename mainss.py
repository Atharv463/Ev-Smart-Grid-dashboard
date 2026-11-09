
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from threading import Lock

app = Flask(__name__)
lock = Lock()

GRID_CAPACITY_W = 100.0
CHARGER_MAX_W = 30.0

telemetry = {
    "voltage": 0.0,
    "current": 0.0,
    "power": 0.0,
    "updated": "Waiting for ESP32"
}

chargers = [
    {"id": 1, "name": "EV Charger 1", "requested": 30, "priority": 1},
    {"id": 2, "name": "EV Charger 2", "requested": 30, "priority": 2},
    {"id": 3, "name": "EV Charger 3", "requested": 30, "priority": 3}
]


def balance_load(grid_load):
    # Reserve capacity for existing grid consumption.
    available = max(0, GRID_CAPACITY_W - grid_load)

    result = []
    remaining = available

    # Lower priority number gets allocated first.
    for charger in sorted(chargers, key=lambda x: x["priority"]):
        allocation = min(
            charger["requested"],
            CHARGER_MAX_W,
            remaining
        )

        remaining -= allocation

        result.append({
            "id": charger["id"],
            "name": charger["name"],
            "requested": charger["requested"],
            "allocated": round(allocation, 2),
            "status": "Charging" if allocation > 0 else "Waiting"
        })

    return result


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/telemetry", methods=["POST"])
def receive_data():
    data = request.get_json(silent=True) or {}

    try:
        voltage = float(data["voltage"])
        current = float(data["current"])

        if not (0 <= voltage <= 60 and 0 <= current <= 10):
            return jsonify({"error": "Measurement out of range"}), 400

    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid sensor data"}), 400

    with lock:
        telemetry.update({
            "voltage": round(voltage, 2),
            "current": round(current, 3),
            "power": round(voltage * current, 2),
            "updated": datetime.now().isoformat(timespec="seconds")
        })

    return jsonify({"message": "Data received"})


@app.route("/api/state")
def get_state():
    with lock:
        readings = telemetry.copy()
        allocations = balance_load(readings["power"])

    return jsonify({
        "telemetry": readings,
        "grid_capacity": GRID_CAPACITY_W,
        "chargers": allocations,
        "total_allocated": round(
            sum(c["allocated"] for c in allocations), 2
        ),
        "available_capacity": round(
            max(0, GRID_CAPACITY_W - readings["power"]
                - sum(c["allocated"] for c in allocations)), 2
        )
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
