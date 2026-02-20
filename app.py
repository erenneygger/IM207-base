from flask import Flask, render_template, request, redirect, session, flash
from datetime import datetime
import qrcode
import io
import base64

app = Flask(__name__)
app.secret_key = "parking_secret"

# ------------------- IN-MEMORY DATABASE -------------------
users = []  # {'fullname','username','password','email','category'}
tickets = []  # {'id','username','plate_number','vehicle_type','slot','entry_time','exit_time','fee','discount_type'}
payments = []

# Parking slots
car_slots = [False] * 10
motorcycle_slots = [False] * 10

# Discounts
DISCOUNTS = {"student": 0.2, "senior": 0.3, "pwd": 0.5, "none": 0}


# =================== HOMEPAGE ===================
@app.route("/")
def home():
    return render_template("home.html")


# =================== LOGIN ===================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        pwd = request.form["password"]

        # Find user by email
        user = next((u for u in users if u["email"] == email and u["password"] == pwd), None)

        if user:
            session["username"] = user["username"]
            session["category"] = user["category"]

            if user["category"] == "Admin":
                return redirect("/dashboard")
            else:
                return redirect("/ticketing_staff")

        flash("Invalid email or password!", "danger")

    return render_template("login.html")


# =================== REGISTER ===================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        uname = request.form["username"]
        pwd = request.form["password"]
        confirm = request.form["confirm"]
        email = request.form["email"]
        category = request.form["category"]

        if pwd != confirm:
            flash("Passwords do not match!", "danger")
            return redirect("/register")

        if any(u["username"] == uname for u in users):
            flash("Username already exists!", "danger")
            return redirect("/register")

        if any(u["email"] == email for u in users):
            flash("Email already registered!", "danger")
            return redirect("/register")

        if category not in ["Admin", "Staff"]:
            flash("Invalid category!", "danger")
            return redirect("/register")

        users.append({
            "fullname": fullname,
            "username": uname,
            "password": pwd,
            "email": email,
            "category": category
        })

        flash("Account created successfully! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


# =================== ADMIN DASHBOARD ===================
@app.route("/dashboard")
def dashboard():
    if "username" not in session or session.get("category") != "Admin":
        flash("Access denied!", "danger")
        return redirect("/login")

    total_tickets = len(tickets)
    active = sum(1 for t in tickets if not t.get("exit_time"))
    income = sum(p["amount"] for p in payments)
    recent = sorted(tickets, key=lambda x: x["entry_time"], reverse=True)[:5]

    car_count = sum(1 for t in tickets if t["vehicle_type"] == "car" and not t.get("exit_time"))
    moto_count = sum(1 for t in tickets if t["vehicle_type"] == "motorcycle" and not t.get("exit_time"))

    return render_template("dashboard.html",
                           total=total_tickets,
                           active=active,
                           income=income,
                           recent=recent,
                           car_count=car_count,
                           moto_count=moto_count)


# =================== ALL REPORTS ===================
@app.route("/reports")
def reports():
    if "username" not in session or session.get("category") != "Admin":
        flash("Access denied!", "danger")
        return redirect("/login")

    total_income = sum(p["amount"] for p in payments)
    completed = [t for t in tickets if t.get("exit_time")]

    return render_template("reports.html",
                           tickets=tickets,
                           total_income=total_income,
                           completed=completed)


# =================== STAFF TICKETING ===================
@app.route("/ticketing_staff", methods=["GET", "POST"])
def ticketing_staff():
    if "username" not in session or session.get("category") != "Staff":
        flash("Access denied!", "danger")
        return redirect("/login")

    if request.method == "POST":
        vehicle_type = request.form["vehicle_type"]
        plate = request.form["plate"]
        discount_type = request.form.get("discount_type", "none")

        if vehicle_type == "car":
            try:
                slot = car_slots.index(False)
                car_slots[slot] = True
            except ValueError:
                flash("No available car slots!", "danger")
                return redirect("/ticketing_staff")
        else:
            try:
                slot = motorcycle_slots.index(False)
                motorcycle_slots[slot] = True
            except ValueError:
                flash("No available motorcycle slots!", "danger")
                return redirect("/ticketing_staff")

        ticket_id = len(tickets) + 1

        ticket = {
            "id": ticket_id,
            "username": session["username"],
            "plate_number": plate,
            "vehicle_type": vehicle_type,
            "slot": slot + 1,
            "entry_time": datetime.now(),
            "exit_time": None,
            "fee": 0,
            "discount_type": discount_type
        }

        tickets.append(ticket)

        flash(f"Ticket created! Slot {slot+1} reserved.", "success")
        return redirect(f"/ticket/{ticket_id}")

    available_car = car_slots.count(False)
    available_moto = motorcycle_slots.count(False)

    return render_template("ticketing_staff.html",
                           available_car=available_car,
                           available_moto=available_moto)


# =================== TICKET VIEW ===================
@app.route("/ticket/<int:ticket_id>")
def ticket(ticket_id):
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)

    if not ticket:
        flash("Ticket not found!", "danger")
        return redirect("/dashboard" if session.get("category") == "Admin" else "/ticketing_staff")

    return render_template("ticketing.html", ticket=ticket)


# =================== EXIT VEHICLE ===================
@app.route("/exit/<int:ticket_id>")
def exit_vehicle(ticket_id):
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)

    if not ticket or ticket.get("exit_time"):
        flash("Invalid exit", "danger")
        return redirect("/dashboard" if session.get("category") == "Admin" else "/ticketing_staff")

    exit_time = datetime.now()
    hours = max(1, int((exit_time - ticket["entry_time"]).total_seconds() // 3600))

    base_fee = hours * 50
    discount = DISCOUNTS.get(ticket.get("discount_type", "none"), 0)
    fee = int(base_fee * (1 - discount))

    ticket["exit_time"] = exit_time
    ticket["fee"] = fee

    payments.append({"ticket_id": ticket_id, "amount": fee})

    if ticket["vehicle_type"] == "car":
        car_slots[ticket["slot"] - 1] = False
    else:
        motorcycle_slots[ticket["slot"] - 1] = False

    flash(f"Vehicle exited. Fee: ₱{fee}", "success")
    return redirect(f"/ticket/{ticket_id}")


# =================== GCASH PAYMENT ===================
@app.route("/gcash/<int:ticket_id>", methods=["GET", "POST"])
def gcash(ticket_id):
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)

    if not ticket:
        flash("Ticket not found!", "danger")
        return redirect("/dashboard" if session.get("category") == "Admin" else "/ticketing_staff")

    if request.method == "POST":
        amount = int(request.form["amount"])
        gcash_number = request.form["gcash_number"]

        if amount >= ticket["fee"]:
            flash("Payment successful!", "success")
        else:
            flash("Insufficient payment!", "danger")

        return redirect(f"/ticket/{ticket_id}")

    return render_template("gcash_payment.html", ticket=ticket)


# =================== ACTIVE SLOTS ===================
@app.route("/active_slots")
def active_slots():
    if "username" not in session:
        flash("Access denied!", "danger")
        return redirect("/login")

    return render_template("active_slots.html",
                           car_slots=car_slots,
                           moto_slots=motorcycle_slots)


# =================== LOGOUT ===================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# =================== RUN APP ===================
if __name__ == "__main__":
    app.run(debug=True)