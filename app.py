
from flask import Flask, render_template, request, redirect, session
import mysql.connector
from datetime import datetime
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "parking_secret"

def db_conn():
    return mysql.connector.connect(**DB_CONFIG)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["admin"] = True
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/")
    db = db_conn()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) AS total FROM tickets")
    total = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS active FROM tickets WHERE exit_time IS NULL")
    active = cur.fetchone()["active"]

    cur.execute("SELECT SUM(amount) AS income FROM payments")
    income = cur.fetchone()["income"] or 0

    return render_template("dashboard.html", total=total, active=active, income=income)

@app.route("/entry", methods=["POST"])
def entry():
    plate = request.form["plate"]
    db = db_conn()
    cur = db.cursor()
    cur.execute("INSERT INTO tickets (plate_number, entry_time) VALUES (%s,%s)",
                (plate, datetime.now()))
    db.commit()
    return redirect("/dashboard")

@app.route("/exit/<int:id>")
def exit_vehicle(id):
    db = db_conn()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM tickets WHERE id=%s", (id,))
    t = cur.fetchone()

    exit_time = datetime.now()
    hours = max(1, int((exit_time - t["entry_time"]).total_seconds() // 3600))
    fee = hours * 50

    cur.execute("UPDATE tickets SET exit_time=%s WHERE id=%s", (exit_time, id))
    cur.execute("INSERT INTO payments (ticket_id, amount) VALUES (%s,%s)", (id, fee))
    db.commit()

    return redirect("/reports")

@app.route("/reports")
def reports():
    if "admin" not in session:
        return redirect("/")

    db = db_conn()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM tickets ORDER BY entry_time DESC")
    tickets = cur.fetchall()

    return render_template("reports.html", tickets=tickets)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
