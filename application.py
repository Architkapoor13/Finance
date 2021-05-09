import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
# FLASK_APP = application.py
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    udetails = db.execute("SELECT * FROM users WHERE id = :user_id",user_id = user_id)
    bdetails = db.execute("SELECT * FROM portfolios WHERE id = :user_id",user_id = user_id)
    transactions = []
    for row in bdetails:
        dic = {}
        shares = lookup(row["symbol"])
        dic["stockowned"] = row["symbol"].upper()
        dic["companyname"] = shares["name"]
        dic["sharesowned"] = row["share"]
        dic["boughtprice"] = usd(row["price"])
        currentprice = float(shares["price"])
        dic["currentprice"] = usd(currentprice)
        sellingamount = currentprice * row["share"]
        dic["amountifsold"] = usd(sellingamount)
        transactions.append(dic)
        # cash = usd(int(udetails[0]["cash"]))
    return render_template("index.html", transactions = transactions)
    # return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        if not symbol or lookup(symbol) == None:
            return apology("Invalid Symbol")
        shares = int(request.form.get("shares"))
        if int(shares)<=0:
            return apology("negative value or zero detected")
        price = lookup(symbol)
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
        total_amount = float(price["price"]) * shares
        if float(cash[0]["cash"])<total_amount:
            return apology("Not enough cash")
        date_time = datetime.now()

        db.execute("INSERT INTO transactions VALUES(:user_id, :symbol, :shares, :price, :time, :totalcost)",user_id=user_id,symbol=symbol.upper(),shares=shares,price=float(price["price"]), time=date_time, totalcost=total_amount)
        portfolio = db.execute("SELECT * FROM portfolios WHERE id = :user_id AND symbol = :symbol",user_id=user_id, symbol = symbol.upper())
        for element in portfolio:
            if float(price["price"]) == float(element["price"]):
                newshares = element["share"] + shares
                db.execute("UPDATE portfolios SET share = :newshares WHERE symbol = :symbol",newshares=newshares, symbol = symbol.upper())
                new_cash = cash[0]["cash"] - total_amount
                db.execute("UPDATE users SET cash = :new_cash WHERE id = :user_id",new_cash=new_cash, user_id=user_id)
                return redirect("/")
        db.execute("INSERT INTO portfolios VALUES (:user_id, :symbol, :shares, :price)",user_id=user_id, symbol=symbol.upper(), shares=shares, price=float(price["price"]))
        new_cash = cash[0]["cash"] - total_amount
        db.execute("UPDATE users SET cash = :new_cash WHERE id = :user_id",new_cash=new_cash, user_id=user_id)
        return redirect("/")

    # return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions where id=:user_id",user_id=user_id)
    return render_template("history.html",transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        sym_info=lookup(symbol)
        usd_value = usd(sym_info["price"])
        return render_template("quoted.html", symbol=sym_info, usd=usd_value)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        if not username:
            return apology("please provide username")
        password = request.form.get("password")
        if not password:
            return apology("Please provide a password")
        confirm = request.form.get("confirmation")
        if not confirm or not password == confirm:
            return apology("Passwords do not match!")
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if len(rows) != 1:
            hash_p = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash_p)", username = username, hash_p = hash_p)
            return redirect("/")
        else:
            return apology("Username already exists")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]
    udetails = db.execute("SELECT * FROM users WHERE id = :user_id",user_id = user_id)
    bdetails = db.execute("SELECT * FROM portfolios WHERE id = :user_id",user_id = user_id)
    if request.method == "GET":
        symbols=[]
        for row in bdetails:
            symbol = row["symbol"].upper()
            if symbol in symbols:
                continue
            symbols.append(symbol)
        prices=[]
        for row in bdetails:
            price = row["price"]
            prices.append(price)
        return render_template("sell.html",symbols = symbols, prices = prices)
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Invalid Symbol")
        price = request.form.get("price")
        shares = int(request.form.get("shares"))
        if shares < 0:
            return apology("Invalid Input")
        boolshare = db.execute("SELECT * FROM portfolios WHERE id = :user_id and symbol = :symbol and price = :price", user_id=user_id,symbol=symbol, price=price)
        if boolshare[0]["share"] < shares:
            return apology("invalid input")
        if shares == boolshare[0]["share"]:
            db.execute("DELETE FROM portfolios WHERE price = :price and symbol = :symbol and id = :user_id", price=price, symbol=symbol, user_id = user_id)
            currentprice = lookup(symbol)
            money = float(currentprice["price"]) * shares
            updated_cash = udetails[0]["cash"] + money
            db.execute("UPDATE users SET cash = :cash WHERE id = :user_id",cash=updated_cash, user_id=user_id)
            db.execute("INSERT INTO transactions VALUES (:user_id, :symbol, :shares, :price, :time, :totalcost)",user_id=user_id, symbol=symbol, shares=negshares, price=float(currentprice["price"]),time=date_time, totalcost=money)
            return redirect("/")
        else:
            updated_share = boolshare[0]["share"] - shares
            currentprice = lookup(symbol)
            money = float(currentprice["price"]) * shares
            updated_cash = udetails[0]["cash"] + money
            negshares = -shares
            date_time = datetime.now()
            db.execute("UPDATE portfolios SET share = :updated_share WHERE id = :user_id and price = :price and symbol = :symbol", updated_share=updated_share, user_id=user_id, price=price, symbol=symbol)
            db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=updated_cash, user_id=user_id)
            db.execute("INSERT INTO transactions VALUES (:user_id, :symbol, :shares, :price, :time, :totalcost)",user_id=user_id, symbol=symbol, shares=negshares, price=float(currentprice["price"]),time=date_time, totalcost=money)
            return redirect("/")



    # return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
