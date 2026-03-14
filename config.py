import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-for-dbms-lab'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb+srv://shanib:shanib@cluster0.okcimp4.mongodb.net/'
    MONGO_DBNAME = 'library_db'
