import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

username = os.environ.get("MYSQL_USER", "root")
password = os.environ.get("MYSQL_PASSWORD", "")
host = os.environ.get("MYSQL_HOST", "127.0.0.1")
port = int(os.environ.get("MYSQL_PORT", "3306"))
database = os.environ.get("MYSQL_DATABASE", "insider_threat")

print(f"Testing MySQL connection with:")
print(f"  Host: {host}")
print(f"  Port: {port}")
print(f"  User: {username}")
print(f"  Password: {'*' * len(password) if password else '(empty)'}")
print(f"  Database: {database}")
print()

try:
    server_url = URL.create(
        "mysql+pymysql", username=username, password=password, host=host, port=port
    )
    server_engine = create_engine(server_url, pool_pre_ping=True)
    
    with server_engine.connect() as connection:
        result = connection.execute(text("SELECT VERSION()"))
        version = result.scalar()
        print(f"✓ MySQL connection successful!")
        print(f"  MySQL Version: {version}")
        
    # Try to create database
    quoted_database = server_engine.dialect.identifier_preparer.quote(database)
    with server_engine.begin() as connection:
        connection.execute(text(
            f"CREATE DATABASE IF NOT EXISTS {quoted_database} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
    print(f"✓ Database '{database}' created or already exists")
    
    server_engine.dispose()
    
except Exception as e:
    print(f"✗ MySQL connection failed: {e}")
    print(f"  Application will fall back to SQLite")
