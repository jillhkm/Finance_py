import os
import sqlite3

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
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


@app.route("/")
@login_required
def index():
    stocklist = db.execute("SELECT symbol, name, units FROM Ownership WHERE User = :user AND NOT units = 0", user = session.get("user_id"))
    valuestocklist = []
    noncurvalue = []
    #changing dictionary to list
    for item in stocklist:
        valuestocklist.append(list(item.values()))
    #getting new price of stock and total value
    for item in valuestocklist:
        item[0] = item[0].upper()
        infodict = lookup(item[0])
        price = infodict.get("price", "none")
        item.append(usd(price))
        totalval = price * item[2]
        noncurvalue.append(totalval)
        item.append(usd(totalval))
    #getting total appraisal
    valuelist = 0
    for item in noncurvalue:
        valuelist += item
    cash = db.execute("SELECT cash FROM users WHERE id = :user", user = session.get("user_id"))
    cash = list(cash[0].values())[0]
    totalassets = cash + valuelist

    return render_template("index.html", valuestocklist = valuestocklist, totalstocks = usd(valuelist), cash = usd(cash), total = usd(totalassets))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        #checks for symbol and no. of shares
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("Please enter symbol of stock to purchase", 402)
        elif not shares:
            return apology("Please enter the number of shares to be purchased", 403)
        try:
            intshare = int(shares)
        except ValueError:
            return apology("Please enter a valid number of shares to purchase", 406)
        if intshare <= 0:
            return apology("Number of shares must be positive", 404)

        # calls yahoo to validate symbol and price
        quotedict = lookup(symbol)
        if bool(quotedict) == False:
            return apology(("Cannot locate stock: {}".format(symbol)), 405)
        cashdict = db.execute("SELECT cash FROM users WHERE id=:username", username = session.get("user_id"))
        cash = cashdict[0].get("cash", "none")
        print("{}".format(cash))
        if (intshare * quotedict.get("price", "none")) > float(cash):
            return apology("You do not have enough money in your account to make this purchase", 407)
        # else buy stock
        else:
            cash -= (float(quotedict.get("price", "none")) * intshare)
            db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash = cash, user = session.get("user_id"))
            checkprior = db.execute("SELECT * FROM Ownership WHERE symbol=:symbol AND user = :user", symbol = symbol, user = session.get("user_id"))
            if bool(checkprior):
                oldamt = db.execute("SELECT units FROM Ownership WHERE symbol=:symbol AND user = :user", symbol = symbol, user = session.get("user_id"))
                oldamt = list(oldamt[0].values())
                oldamt = oldamt[0]
                newamt = oldamt + intshare
                print (newamt)
                db.execute("UPDATE ownership SET units = :units WHERE symbol = :symbol", units = newamt, symbol = symbol)
                db.execute("INSERT INTO History VALUES (:username, :Bought, :symbol, :name, +:number, :price, :cash)", username = session.get("user_id"), Bought = "bought",
                symbol = symbol, name = quotedict.get("name", "none"), number = intshare, price = quotedict.get("price", "none"), cash = cash)
            else:
                db.execute("INSERT INTO Ownership VALUES (:username, :symbol, :name, :number)", username = session.get("user_id"),
                symbol = symbol, name = quotedict.get("name", "none"), number = intshare)
            db.execute("INSERT INTO History VALUES (:username, :Bought, :symbol, :name, +:number, :price, :cash)", username = session.get("user_id"),
                Bought = "Bought", symbol = symbol, name = quotedict.get("name", "none"), number = intshare, price = quotedict.get("price", "none"), cash = cash)
            return index()

    #method via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    stocklist = db.execute("SELECT action, symbol, name, units, price, cash FROM History WHERE id = :user", user = session.get("user_id"))
    valuestocklist = []
    noncurvalue = []
    #changing dictionary to list
    for item in stocklist:
        valuestocklist.append(list(item.values()))
    #getting new price of stock and total value
    for item in valuestocklist:
        item[0] = item[0].capitalize()
        item[1] = item[1].upper()
        item[4] = usd(item[4])
        item[5] = usd(item[5])
        infodict = lookup(item[1])
        price = infodict.get("price", "none")
        totalval = price * item[3]
        noncurvalue.append(totalval)
    #getting total appraisal
    valuelist = 0
    for item in noncurvalue:
        valuelist += item
    cash = db.execute("SELECT cash FROM users WHERE id = :user", user = session.get("user_id"))
    cash = list(cash[0].values())[0]
    totalassets = cash + valuelist

    return render_template("history.html", valuestocklist = valuestocklist, totalstocks = usd(valuelist), cash = usd(cash), total = usd(totalassets))



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

@app.route("/sold", methods=["GET", "POST"])
@login_required
def sold():
    if request.method == "POST":
        return index()


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if request.form.get("quote") == "":
            return render_template("quote.html")
        quotedict = lookup(request.form.get("quote"))
        if bool(quotedict) == False:
            return apology(("Cannot locate stock: {}".format(request.form.get("quote"))), 403)
        else:
            return render_template("quoinfo.html", symbol = quotedict.get("symbol", "none"), name = quotedict.get("name", "none"), price = usd(quotedict.get("price", "none")) )
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide a username", 403)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)
        hash = generate_password_hash(request.form.get("password"))
        user = request.form.get("username")
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username= user, hash= hash)
        if not result:
            return apology("Username is already registered", 403)
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        return render_template("registered.html")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        #checks for symbol and no. of shares
        symbol = (request.form.get("symbol")).lower()
        shares = request.form.get("shares")
        if not symbol:
            return apology("Please enter symbol of stock to be sold", 402)
        elif not shares:
            return apology("Please enter the number of shares to be sold", 403)
        try:
            intshare = int(shares)
        except ValueError:
            return apology("Please enter a valid number of shares to be sold", 406)
        if intshare <= 0:
            return apology("Number of shares must be positive", 404)

        # calls yahoo to validate symbol and price
        quotedict = lookup(symbol)
        if bool(quotedict) == False:
            return apology(("Cannot locate stock: {}".format(symbol)), 405)
        cashdict = db.execute("SELECT cash FROM users WHERE id=:username", username = session.get("user_id"))
        cash = cashdict[0].get("cash", "none")
        # check that stock is in ownership
        checkprior = db.execute("SELECT * FROM Ownership WHERE symbol=:symbol AND user = :username", symbol = symbol, username = session.get("user_id"))
        if bool(checkprior):
            oldamt = db.execute("SELECT units FROM Ownership WHERE symbol=:symbol AND user = :username", symbol = symbol, username = session.get("user_id"))
            oldamt = list(oldamt[0].values())
            oldamt = oldamt[0]
            #check if amt of stock exists
            if oldamt < intshare:
                return apology("Cannot sell more shares than you own", 408)
            else:
                newamt = oldamt - intshare
                db.execute("UPDATE ownership SET units = :units WHERE symbol = :symbol", units = newamt, symbol = symbol)
                profit = (float(quotedict.get("price", "none")) * intshare)
                cash += profit
                db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash = cash, user = session.get("user_id"))
                db.execute("INSERT INTO History VALUES (:username, :sold, :symbol, :name, -:number, :price, :cash)", username = session.get("user_id"), sold = "Sold",
                symbol = symbol, name = quotedict.get("name", "none"), number = intshare, price = quotedict.get("price", "none"), cash = cash)
                return render_template("sold.html", shares = intshare, name = quotedict.get("name", "none"), owned = newamt, profit = usd(profit), cash = usd(cash))
        else:
            return apology("You do not own this stock", 407)
    #method via GET
    else:
        return render_template("sell.html")



def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
