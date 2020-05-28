import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify, flash
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
		flash('You are already logged in', 'warning')
		return redirect(url_for("index"))
	else:
		if request.method == 'POST':
			username = request.form['username']
			password = request.form['password']

			user = db.execute("SELECT * \
								FROM users \
								WHERE username = :username",
								{"username": username}
							).fetchone()

			if user == None or not check_password_hash(user["password_hash"], password):
				flash('Either your username or password is wrong. Please try again.', 'danger')
				return render_template('login.html')
			else:
				flash('You have successfully logged in!', 'success')
				session['username'] = username
				return redirect(url_for('index'))
		else:
			return render_template('login.html')

@app.route("/logout")
def logout():
	""" Log users out """
	
	# remove the username from the session if it is there
	session.pop('username', None)
	flash('You have logged out!', 'success')
	return redirect(url_for('index'))

@app.route("/register", methods=['GET','POST'])
def register():
	''' Register users '''

	if request.method == "POST":
		new_username = request.form['username']
		new_password = request.form['password']

		if db.execute("SELECT * \
						FROM users \
						WHERE username = :new_username",
						{ "new_username": new_username}
					).rowcount > 0:
			flash('this username has been taken, please try another one', 'danger')
			return render_template('register.html')
		else:
			db.execute("INSERT INTO users (username, password_hash) \
						VALUES (:username, :password_hash)",
						{"username": new_username,
						"password_hash": generate_password_hash(new_password)}
					)
			db.commit()

		return redirect(url_for('login')) # TODO: add message that registration is successful
	else:
		return render_template('register.html')


@app.route("/search")
def search():
	""" Get search results """

	if session.get("username") is None:
		return redirect(url_for("login"))

	search_term = request.args.get("book")
	search_term = search_term.strip()

	if not search_term:
		flash('search field cannot be empty', 'danger')
		return render_template('index.html')

	query = "%" + request.args.get("book") + "%"

	rows = db.execute("SELECT * FROM books \
						WHERE isbn LIKE :query \
						OR title LIKE :query \
						OR author LIKE :query",
						{"query": query}
					)

	num_books_found = rows.rowcount	

	books = rows.fetchall()
	return render_template("results.html", search_term=search_term, num_books=num_books_found, books=books)

@app.route("/books/<string:isbn>", methods=['GET','POST'])
def book(isbn):

	if session.get("username") is None:
		return redirect(url_for("login"))

	if request.method == "POST":
		# check for existing reviews by current user
		username = session['username']

		rows = db.execute("SELECT * \
							FROM reviews \
							WHERE username = :username \
							AND isbn = :isbn",
							{"username": username,
							"isbn": isbn}
						)

		if rows.rowcount > 0:
			flash('You have already submitted a review for this book', 'danger')
			return redirect(url_for('book', isbn=isbn))


		rating = request.form['rating']
		print(rating)
		comment = request.form['comment']
		print(comment)

		if comment:
			db.execute("INSERT INTO reviews (username, isbn, rating, comment) \
						VALUES (:username, :isbn, :rating, :comment)",
						{"username": username,
						"isbn": isbn,
						"rating": rating,
						"comment": comment}
						)
			db.commit()

		flash('You have added a review!', 'success')
		return redirect(url_for('book', isbn=isbn))
	else:
		# find the book the user has selected
		book = db.execute("SELECT * \
							FROM Books \
							WHERE isbn = :isbn \
							LIMIT 1",
							{"isbn": isbn}
						).fetchall()
		book = book[0]

		# find all ratings and reviews for the selected book
		reviews = db.execute("SELECT username, comment, rating \
								FROM reviews \
								WHERE isbn = :isbn",
								{'isbn': isbn}
							).fetchall()

		# Read API key from env variable
		key = os.getenv("GOODREADS_KEY")

		# Query the api with key and ISBN as parameters
		json_response = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": isbn}).json()
		goodreads_review_statistics = json_response["books"][0]

		# return the information, ratings and reviews of the selected book
		return render_template("book.html", book=book, reviews=reviews, goodreads_review_statistics=goodreads_review_statistics)

@app.route("/api/<string:isbn>", methods=['GET'])
def api(isbn):
	""" API access for all users to get book details by isbn """
	
	# check if the book exists in our database
	rows = db.execute('SELECT title, author, year, isbn \
						FROM books \
						WHERE isbn = :isbn',
						{"isbn": isbn}
					)

	if rows.rowcount > 0:
		row = rows.fetchone();

		# get review statistics from goodreads
		key = os.getenv("GOODREADS_KEY")
		json_response = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": isbn}).json()
		goodreads_review_statistics = json_response["books"][0]

		return jsonify(title=row.title,
						author=row.author,
						year=row.year,
						isbn=row.isbn,
						review_count=goodreads_review_statistics["work_ratings_count"],
						average_score=float(goodreads_review_statistics["average_rating"])
					)
	else:
		return jsonify(code=404,message="We do not have a book with ISBN number " + isbn + ".")
