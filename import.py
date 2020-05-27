import os, csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# database engine object from SQLAlchemy that manages connections to the database
engine = create_engine(os.getenv("DATABASE_URL"))

# create a 'scoped session' that ensures different users' interactions with the
# database are kept separate
db = scoped_session(sessionmaker(bind=engine))

f = open("books.csv")
reader = csv.reader(f)
next(reader, None)  # skip the headers
for isbn, title, author, year in reader: # loop gives each column a name
	db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
              {"isbn": isbn, "title": title, "author": author, "year": year}) # substitute values from CSV line into SQL command, as per this dict
	print(f"Added book {title} by {author} in {year} with ISBN: {isbn} to database.")
db.commit() # transactions are assumed, so close the transaction finished