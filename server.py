from datetime import datetime
from hashlib import sha256
from pathlib import Path
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, jsonify, request


app = Flask(__name__)

LOG_FILE = Path("temperature_log.csv")
MERKLE_FILE = Path("merkle_state.txt")


# --------------------------------------------------    
# EMAIL SETTINGS
# --------------------------------------------------

EMAIL_RECIPIENTS = [
    ""
]

EMAIL_ADDRESS = ""
EMAIL_PASSWORD = ""


# --------------------------------------------------
# HASHING / MERKLE
# --------------------------------------------------

def hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return ""

    level = hashes[:]

    while len(level) > 1:

        if len(level) % 2 == 1:
            level.append(level[-1])

        next_level = []

        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            parent_hash = hash_text(combined)
            next_level.append(parent_hash)

        level = next_level

    return level[0]


def load_records():
    records = []

    if not LOG_FILE.exists():
        return records

    with LOG_FILE.open("r", encoding="utf-8") as file:

        for line in file:
            line = line.strip()

            if not line:
                continue

            parts = line.split(",")

            if len(parts) >= 3:
                timestamp = parts[0]
                temperature = parts[1]
                leaf_hash = parts[2]

                records.append({
                    "timestamp": timestamp,
                    "temperature": temperature,
                    "leaf_hash": leaf_hash
                })

    return records


def load_leaf_hashes():
    records = load_records()

    return [
        record["leaf_hash"]
        for record in records
    ]


def save_merkle_state(root_hash: str, leaf_count: int):
    timestamp = datetime.now().isoformat(timespec="seconds")

    with MERKLE_FILE.open("w", encoding="utf-8") as file:
        file.write(f"updated_at={timestamp}\n")
        file.write(f"leaf_count={leaf_count}\n")
        file.write(f"merkle_root={root_hash}\n")


# --------------------------------------------------
# EMAIL
# --------------------------------------------------

def send_email():
    msg = MIMEMultipart()

    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ", ".join(EMAIL_RECIPIENTS)
    msg["Subject"] = ""

    records = load_records()

    if records:
        temperatures = [
            float(record["temperature"])
            for record in records
        ]

        latest = temperatures[-1]
        minimum = min(temperatures)
        maximum = max(temperatures)
        average = sum(temperatures) / len(temperatures)

        leaf_hashes = load_leaf_hashes()
        merkle_root = build_merkle_root(leaf_hashes)

        body = f"""


Latest temperature: {latest:.1f} F




Generated:
{datetime.now().isoformat(timespec="seconds")}


"""

    else:
        body = """
Hey you're awesome!



Sincerely,
Taylor
"""

    msg.attach(
        MIMEText(body, "plain")
    )

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as server:

            server.login(
                EMAIL_ADDRESS,
                EMAIL_PASSWORD
            )

            server.sendmail(
                EMAIL_ADDRESS,
                EMAIL_RECIPIENTS,
                msg.as_string()
            )

        print("Email sent successfully.")

        return True

    except Exception as e:
        print(f"Error sending email: {e}")

        return False


# --------------------------------------------------
# TEMPERATURE UPLOAD
# --------------------------------------------------

@app.post("/temperature")
def receive_temperature():

    data = request.get_json(silent=True)

    if not data or "temperature_f" not in data:
        return jsonify({
            "error": "temperature_f missing"
        }), 400

    try:
        temperature = float(data["temperature_f"])

    except (TypeError, ValueError):
        return jsonify({
            "error": "temperature_f must be numeric"
        }), 400

    timestamp = datetime.now().isoformat(timespec="seconds")

    record = f"{timestamp}|{temperature:.1f}"

    leaf_hash = hash_text(record)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(
            f"{timestamp},{temperature:.1f},{leaf_hash}\n"
        )

    leaf_hashes = load_leaf_hashes()

    merkle_root = build_merkle_root(
        leaf_hashes
    )

    save_merkle_state(
        merkle_root,
        len(leaf_hashes)
    )

    print()
    print(
        f"{timestamp} | "
        f"{temperature:.1f} F"
    )

    print(
        f"Leaf hash:   "
        f"{leaf_hash}"
    )

    print(
        f"Merkle root: "
        f"{merkle_root}"
    )

    print()

    return jsonify({
        "received": True,
        "timestamp": timestamp,
        "temperature_f": temperature,
        "leaf_hash": leaf_hash,
        "merkle_root": merkle_root,
        "leaf_count": len(leaf_hashes)
    }), 200


# --------------------------------------------------
# MERKLE STATUS
# --------------------------------------------------

@app.get("/merkle")
def get_merkle_state():

    hashes = load_leaf_hashes()

    root = build_merkle_root(
        hashes
    )

    return jsonify({
        "leaf_count": len(hashes),
        "merkle_root": root
    }), 200


# --------------------------------------------------
# VERIFY LOG
# --------------------------------------------------

@app.get("/verify")
def verify_log():

    records = load_records()

    if not records:
        return jsonify({
            "verified": True,
            "records": 0,
            "merkle_root": ""
        }), 200

    calculated_hashes = []

    for record in records:

        canonical = (
            f"{record['timestamp']}|"
            f"{float(record['temperature']):.1f}"
        )

        calculated_hash = hash_text(
            canonical
        )

        if calculated_hash != record["leaf_hash"]:

            return jsonify({
                "verified": False,
                "bad_record": record["timestamp"]
            }), 200

        calculated_hashes.append(
            calculated_hash
        )

    root = build_merkle_root(
        calculated_hashes
    )

    return jsonify({
        "verified": True,
        "records": len(records),
        "merkle_root": root
    }), 200


# --------------------------------------------------
# TEMPERATURE REPORT
# --------------------------------------------------

@app.get("/report")
def temperature_report():

    records = load_records()

    if not records:
        return jsonify({
            "count": 0
        }), 200

    temperatures = [
        float(record["temperature"])
        for record in records
    ]

    return jsonify({
        "count": len(temperatures),
        "latest": temperatures[-1],
        "minimum": min(temperatures),
        "maximum": max(temperatures),
        "average": round(
            sum(temperatures) / len(temperatures),
            1
        )
    }), 200


# --------------------------------------------------
# EMAIL REPORT
# --------------------------------------------------

@app.post("/email-report")
def email_report():

    if send_email():

        return jsonify({
            "sent": True
        }), 200

    return jsonify({
        "sent": False
    }), 500


# --------------------------------------------------
# SERVER STATUS
# --------------------------------------------------

@app.get("/health")
def health():

    return jsonify({
        "status": "online",
        "time": datetime.now().isoformat(
            timespec="seconds"
        )
    }), 200


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )