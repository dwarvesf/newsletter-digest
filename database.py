from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    email_uid = Column(String, nullable=False)
    email_time = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    criteria = Column(Text, nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_article(db, email_uid, email_time, title, description, url, criteria):
    # Check if an article with the same URL already exists
    existing_article = db.query(Article).filter(Article.url == url).first()
    if existing_article:
        return existing_article  # Return the existing article

    # If no existing article, proceed with saving
    db_article = Article(email_uid=email_uid, email_time=email_time, title=title, 
                         description=description, url=url, criteria=str(criteria))
    db.add(db_article)
    try:
        db.commit()
        db.refresh(db_article)
        return db_article
    except IntegrityError:
        db.rollback()
        # In case of a race condition, fetch the article again
        return db.query(Article).filter(Article.url == url).first()

def get_articles(db, date_from=None, limit=None):
    query = db.query(Article)
    if date_from:
        query = query.filter(Article.email_time >= date_from)
    query = query.order_by(Article.email_time.desc())
    if limit:
        query = query.limit(limit)
    return query.all()
