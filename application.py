import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 50
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

def des(num):
    return int(num * 100) / 100


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session.get("user_id")
    stocks = db.execute("SELECT * FROM stock WHERE userid = :userid", userid=userid)
    stock_val = 0

    # Show default id user does nt have any stocks
    if len(stocks) == 0:
        return render_template("empty.html", message="No information to display")
    print(len(stocks))
    for i in range(len(stocks)):

        sym = stocks[i]['sym']
        up = lookup(sym)
        val = up['price'] * stocks[i]['quantity']
        stocks[i].update({'name': up['name']})
        stocks[i].update({'val': usd(val)})
        stocks[i].update({'price': usd(up['price'])})
        stock_val += val

    cb = db.execute("SELECT * FROM users WHERE id = :userid", userid=userid)

    total_bal = usd(cb[0]['cash'] + stock_val)
    stock_val = usd(stock_val)
    cash_bal = usd(cb[0]['cash'])
    l = len(stocks)

    return render_template("index.html", stocks=stocks, stock_val=stock_val, cash_bal=cash_bal, total_bal=total_bal, l=l)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        if not request.form.get("shares") or not request.form.get("symbol"):
            return apology("Fill all de fields nah!S", 403)
        else:
            shares = request.form.get("shares")
            symbol = request.form.get("symbol")

            try:
                shares = int(shares)
            except ValueError:
                return apology("Put a valid share joor", 400)

            # validate shares more that 1
            if shares < 1:
                return apology("You neva put quantity of stock", 400)
            result = lookup(symbol)
            if result == None:
                return apology("The Symbol you select no valid o!", 400)
            else:
                userid = session.get("user_id")
                price = des(result["price"])
                amt = price * shares
                user = db.execute("SELECT cash FROM users WHERE id = :id", id=userid)
                bal = des(user[0]['cash'])
                if bal < amt:
                    return apology("You do not have enough balance to buy this stock", 400)
                nbal = des(bal - amt)
                # update transaction
                db.execute("INSERT INTO transactions (user, type, symbol, quant, prev, new, price) VALUES (:userid, :type, :sym, :shares, :bal, :nbal, :price)", userid=userid,
                           type="BUY", sym=symbol, shares=shares, bal=bal, nbal=nbal, price=price)

                # update cash bal
                db.execute("UPDATE users SET cash = :nbal WHERE id = :userid", nbal=nbal, userid=userid)

                # record stock
                stock = db.execute("SELECT quantity FROM stock WHERE userid = :id AND sym = :sym", id=userid, sym=symbol)

                if stock == []:
                    db.execute("INSERT INTO stock (userid, sym, quantity) VALUES (:userid, :sym, :quant)",
                               userid=userid, sym=symbol, quant=shares)
                else:
                    nstock = int(stock[0]["quantity"]) + shares
                    print(nstock)
                    db.execute("UPDATE stock SET quantity = :nstock WHERE userid = :id AND sym = :sym",
                               nstock=nstock, id=userid, sym=symbol)
                return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session.get("user_id")
    history = db.execute("SELECT * FROM transactions WHERE user = :userid", userid=userid)
    if (len(history) == 0):
        return render_template("empty.html", message="No history to display")
    cash_bal = db.execute("SELECT cash FROM users WHERE id = :id", id=userid)

    # format USD values to money
    for i in range(len(history)):
        history[i]['prev'] = usd(history[i]['prev'])
        history[i]['new'] = usd(history[i]['new'])

    return render_template("history.html", history=history, l=len(history), cash_bal=usd(cash_bal[0]['cash']))


@app.route("/register", methods=["GET", "POST"])
def register():
    """ Register a new user or return register page"""

    # forget any user id
    session.clear()

    # return register page if method is get
    if request.method == "POST":
        # check whether user filled out all inputs
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("you must fill out all fields", 400)
        # check if passwords are the same
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("Password Mismatch", 400)
        else:
            row = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            if len(row) >= 1:
                return apology("Person don take this username", 400)
            hash = generate_password_hash(request.form.get("password"))
            userid = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                                username=request.form.get("username").strip(), hash=hash)

            # set new user id in session
            session["user_id"] = userid

            # Redirect user to home page
            return redirect("/")
    else:
        return render_template("register.html")


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
                          username=request.form.get("username").strip())

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
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("You neva put symbol o", 400)
        symbol = request.form.get("symbol")
        result = lookup(symbol)
        if result == None:
            return apology("The Symbol ypu select no valid o!", 400)
        else:
            result["price"] = usd(des(result["price"]))
            return render_template("quoted.html", result=result)
    else:
        return render_template("quote.html")


# redirect if user attempts to call quoted with query
@app.route("/quoted", methods=["GET"])
@login_required
def quoted():
    return redirect("/quote")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    userid = session.get("user_id")
    options = db.execute("SELECT * FROM stock WHERE userid = :userid", userid=userid)
    l = len(options)
    if request.method == "POST":
        # check all input are valid
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("check all input field naa!", 400)

        sym = request.form.get("symbol")
        quant = int(request.form.get("shares"))
        syms = [options[i]['sym'] for i in range(l)]
        if not sym in syms:
            return apology("You wan sell stock wey you no get?!", 400)

        s = [options[i] for i in range(l) if options[i]['sym'] == sym]

        if quant > s[0]["quantity"]:
            return apology("You no get the quantity you wan sell, reduce hand", 400)

        q = s[0]['quantity'] - quant

        # get actual price
        res = lookup(sym)
        price = des(res['price'])
        pz = des(quant * price)

        cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)

        amt = des(cash[0]['cash'] + pz)

        # update cash
        db.execute("UPDATE users SET cash = :amt WHERE id = :userid", amt=amt, userid=userid)

        # update new quantity
        db.execute("UPDATE stock SET quantity = :q WHERE userid = :userid AND sym = :sym", q=q, userid=userid, sym=sym)

        # update transaction
        db.execute("INSERT INTO transactions (user, type, symbol, quant, prev, new, price) VALUES (:userid, :type, :sym, :shares, :bal, :nbal, :price)", userid=userid,
                   type="SELL", sym=sym, shares=quant, bal=des(cash[0]['cash']), nbal=amt, price=price)
        return redirect("/")
    else:
        if l == 0:
            return render_template("empty.html", message="No stocks to sell")
        return render_template("sell.html", options=options, l=l)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
