import os
import sys
from sqlalchemy import Table, Column, ForeignKey, Integer, String, Date, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()


class Users(Base):

    __tablename__ = 'users'

    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    email = Column(String(80), nullable = False)
    picture = Column(String(250))


class Books(Base):

    __tablename__ = 'books'

    id = Column(Integer, primary_key = True)
    date = Column(Date(), nullable = False)
    name = Column(String(160), nullable = False)
    ISBN = Column(String(20))
    price = Column(Integer, nullable = False)
    course = Column(String(8), nullable = False)
    semester = Column(String(8))
    prof = Column(String(40))
    user_id = Column(Integer, ForeignKey('users.id'))
    users = relationship(Users)


# Keep at end of file
engine = create_engine('sqlite:///bookconnect.db')


Base.metadata.create_all(engine)
