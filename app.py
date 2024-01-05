import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        """Show portfolio of stocks"""
        holdings = db.execute(
            "SELECT * FROM holdings WHERE userid = ?;", session["user_id"]
        )
        total = 0
        availablecash = db.execute(
            "SELECT cash FROM users WHERE id = ?;", session["user_id"]
        )
        for holding in holdings:
            # loop the list of stock dicts
            holding.update({"current_price": lookup(holding["stock"])["price"]})
            holding["current_value"] = holding["current_price"] * holding["shares"]
            total += holding["current_value"]

            holding["current_value"] = usd(holding["current_value"])
            holding["current_price"] = usd(holding["current_price"])

        totalassets = usd(total + availablecash[0]["cash"])
        totalcash = usd(availablecash[0]["cash"])
        total = usd(total)
        return render_template(
            "index.html",
            holdings=holdings,
            total=total,
            totalcash=totalcash,
            totalassets=totalassets,
        )
    else:
        # if arrived by post process adding cash
        addcash = request.form.get("addcash")
        if not addcash.isnumeric():
            return apology("please enter a number", 400)
        addcash = int(addcash)
        availablecash = db.execute(
            "SELECT cash FROM users WHERE id = ?;", session["user_id"]
        )
        cash = availablecash[0]["cash"] + addcash
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", cash, session["user_id"])
        return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("need a stock symbol", 400)
        if not shares:
            return apology("input shares please", 400)

        def is_integer(n):
            try:
                float(n)
            except ValueError:
                return False
            else:
                return float(n).is_integer()

        if not is_integer(shares):
            return apology("whole number of shares please", 400)
        if int(shares) <= 0:
            return apology("positive number of shares please", 400)
        luquote = lookup(symbol)
        if luquote == None:
            return apology("need a correct symbol", 400)
        convertedquote = usd(luquote["price"])
        availablecash = db.execute(
            "SELECT cash FROM users WHERE id = ?;", session["user_id"]
        )
        print(availablecash[0]["cash"])
        if (luquote["price"] * int(shares)) > float(availablecash[0]["cash"]):
            return apology("you too poor", 400)
        else:
            currentDateAndTime = datetime.now()
            year = currentDateAndTime.year
            month = currentDateAndTime.month
            day = currentDateAndTime.day
            hour = currentDateAndTime.hour
            minute = currentDateAndTime.minute
            second = currentDateAndTime.second
            cost = luquote["price"] * int(shares)
            db.execute(
                "INSERT INTO purchases (userid, stock, price, shares, cost, year, month, day, hour, minute, second) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                session["user_id"],
                symbol,
                luquote["price"],
                int(shares),
                cost,
                year,
                month,
                day,
                hour,
                minute,
                second,
            )
            availablecash[0]["cash"] -= cost
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?;",
                availablecash[0]["cash"],
                session["user_id"],
            )

            # add shares to the stocks held table
            purchasedstock = db.execute(
                "SELECT * FROM holdings WHERE userid = ? AND stock = ?;",
                session["user_id"],
                symbol,
            )
            if len(purchasedstock) > 0:
                currentstocks = purchasedstock[0]["shares"] + int(shares)
                db.execute(
                    "UPDATE holdings SET shares = ? WHERE userid = ? AND stock = ?;",
                    currentstocks,
                    session["user_id"],
                    symbol,
                )
                # add the number to the old number
            else:
                # create a new entry for the given stock symbol
                db.execute(
                    "INSERT INTO holdings (userid, stock, shares) VALUES(?, ?, ?);",
                    session["user_id"],
                    symbol,
                    int(shares),
                )
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    if request.method == "POST":
        oldpassword = request.form.get("oldpassword")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        print(rows)

        # Ensure username was submitted
        if not oldpassword:
            return apology("must enter password", 400)

        elif not check_password_hash(rows[0]["hash"], request.form.get("oldpassword")):
            return apology("invalid password", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure confirmation of passeword is correct
        elif password != confirmation:
            return apology("confirmation must match", 400)

        # Check password min 8 chars
        if len(password) < 8:
            return apology("password min 8 characters", 400)

        # Check password contains non alphanumberic numbers etc
        caps = False
        lower = False
        numeric = False
        nonalpha = False
        for char in password:
            if char.isupper():
                caps = True
            if char.islower():
                lower = True
            if char.isdigit():
                numeric = True
            if char.isalnum():
                nonalpha = True
        if not caps:
            return apology("at least 1 capital letter", 400)
        if not lower:
            return apology("at least 1 lower case letter", 400)
        if not numeric:
            return apology("at least 1 number", 400)
        if not nonalpha:
            return apology("at least 1 symbol", 400)

        # Register new user
        db.execute(
            "UPDATE users SET hash=? WHERE id=?;",
            generate_password_hash(password),
            session["user_id"],
        )
        return render_template("login.html")
    else:
        return render_template("changepassword.html")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    """Show history of transactions"""
    if request.method == "GET":
        """Show portfolio of stocks"""
        history = db.execute(
            "SELECT * FROM purchases WHERE userid = ?;", session["user_id"]
        )
        for row in history:
            row["price"] = usd(row["price"])
            row["cost"] = usd(row["cost"])
        return render_template("history.html", history=history)
    else:
        db.execute("UPDATE users SET cash = 10000 WHERE id = ?;", session["user_id"])
        return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("need a stock symbol", 400)
        luquote = lookup(symbol)
        if luquote == None:
            return apology("need a correct symbol", 400)
        convertedquote = usd(luquote["price"])
        return render_template("quoted.html", luquote=convertedquote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        print(username)
        print(password)
        print(confirmation)
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure confirmation of passewordis correct

        elif password != confirmation:
            return apology("confirmation must match", 400)

        # Check password min 8 chars
        if len(password) < 8:
            return apology("password min 8 characters", 400)

        # Check password contains non alphanumberic numbers etc
        caps = False
        lower = False
        numeric = False
        nonalpha = False
        for char in password:
            if char.isupper():
                caps = True
            if char.islower():
                lower = True
            if char.isdigit():
                numeric = True
            if char.isalnum():
                nonalpha = True
        if not caps:
            return apology("at least 1 capital letter", 400)
        if not lower:
            return apology("at least 1 lower case letter", 400)
        if not numeric:
            return apology("at least 1 number", 400)
        if not nonalpha:
            return apology("at least 1 symbol", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) > 0:
            return apology("username already in use", 400)

        # Register new user
        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?);",
            username,
            generate_password_hash(password),
        )
        return render_template("login.html")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("need a stock symbol", 400)
        if not shares:
            return apology("input shares please", 400)

        def is_integer(n):
            try:
                float(n)
            except ValueError:
                return False
            else:
                return float(n).is_integer()

        if not is_integer(shares):
            return apology("whole number of shares please", 400)
        if int(shares) <= 0:
            return apology("positive number of shares please", 400)
        luquote = lookup(symbol)
        if luquote == None:
            return apology("need a correct symbol", 400)
        convertedquote = usd(luquote["price"])
        availablecash = db.execute(
            "SELECT cash FROM users WHERE id = ?;", session["user_id"]
        )
        print(availablecash[0]["cash"])
        ownedstock = db.execute(
            "SELECT * FROM holdings WHERE userid = ? AND stock = ?;",
            session["user_id"],
            symbol,
        )
        if ownedstock[0]["shares"] < int(shares):
            return apology("not enough shares", 400)
        else:
            currentDateAndTime = datetime.now()
            year = currentDateAndTime.year
            month = currentDateAndTime.month
            day = currentDateAndTime.day
            hour = currentDateAndTime.hour
            minute = currentDateAndTime.minute
            second = currentDateAndTime.second
            cost = luquote["price"] * int(shares)
            db.execute(
                "INSERT INTO purchases (userid, stock, price, shares, cost, year, month, day, hour, minute, second) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                session["user_id"],
                symbol,
                luquote["price"],
                -int(shares),
                cost,
                year,
                month,
                day,
                hour,
                minute,
                second,
            )
            availablecash[0]["cash"] += cost
            db.execute(
                "UPDATE users SET cash = ? WHERE id = ?;",
                availablecash[0]["cash"],
                session["user_id"],
            )

            # add shares to the stocks held table
            ownedstock = db.execute(
                "SELECT * FROM holdings WHERE userid = ? AND stock = ?;",
                session["user_id"],
                symbol,
            )
            if ownedstock[0]["shares"] > int(shares):
                currentstocks = ownedstock[0]["shares"] - int(shares)
                db.execute(
                    "UPDATE holdings SET shares = ? WHERE userid = ? AND stock = ?;",
                    currentstocks,
                    session["user_id"],
                    symbol,
                )
                # add the number to the old number
            else:
                # create a new entry for the given stock symbol
                db.execute(
                    "DELETE FROM holdings WHERE userid = ? AND stock = ?;",
                    session["user_id"],
                    symbol,
                )
        return redirect("/")
    else:
        availablestocks = db.execute(
            "SELECT * FROM holdings WHERE userid = ?;", session["user_id"]
        )
        return render_template("sell.html", availablestocks=availablestocks)
