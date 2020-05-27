import os

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
	if session.get("username") is None:
		return redirect(url_for("login"))

	return render_template("index.html")

@app.route("/login", methods=['GET','POST'])
def login():
	""" Login users in """

	if not session.get("username") is None:
		error = "You are already logged in"
		return redirect(url_for("index"))
	else:
		error = None
		if request.method == 'POST':
			username = request.form['username']
			password = request.form['password']

			user = db.execute("Select * FROM users WHERE username=:username" , {"username": username}).fetchone()

			if user == None or not check_password_hash(user["password_hash"], password):
				error = 'Either your username or password is wrong. Please try again.'
				return render_template('login.html', error=error)
			else:
				session['username'] = username
				return redirect(url_for('index'))
		else:
			return render_template('login.html')

@app.route("/logout")
def logout():
	""" Log users out """
	
	# remove the username from the session if it is there
	session.pop('username', None)
	return redirect(url_for('index'))

@app.route("/register", methods=['GET','POST'])
def register():
	''' Register users '''

	if request.method == "POST":
		new_username = request.form['username']
		new_password = request.form['password']

		if db.execute("Select * from users WHERE username = :new_username", { "new_username": new_username}).rowcount > 0:
			error = "this username has been taken, please try another one"
			return render_template('register.html', error=error)
		else:
			db.execute("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)", {"username": new_username, "password_hash": generate_password_hash(new_password)})
			db.commit()

		return redirect(url_for('login')) # TODO: add message that registration is successful
	else:
		return render_template('register.html')


@app.route("/search")
def search():
	""" Get search results """
	search_term = request.args.get("book")
	search_term = search_term.strip()

	if not search_term:
		return render_template('index.html', error="search field cannot be empty")

	query = "%" + request.args.get("book") + "%"

	rows = db.execute("SELECT * FROM books WHERE \
						isbn LIKE :query OR \
						title LIKE :query OR \
						author LIKE :query",
						{"query": query})

	num_books_found = rows.rowcount	

	books = rows.fetchall()
	return render_template("results.html", num_books=num_books_found, books=books)