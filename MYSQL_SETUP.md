# MySQL Setup Guide for Insider Threat Dashboard

## Overview
The application is already configured to use MySQL for dataset storage. When MySQL is available, it will automatically store datasets and analysis results in MySQL. If MySQL is not available, it falls back to SQLite.

## Installation Steps

### Option 1: Install MySQL Server (Recommended)

1. **Download MySQL Installer for Windows**
   - Visit: https://dev.mysql.com/downloads/installer/
   - Download "MySQL Installer for Windows"

2. **Run the Installer**
   - Choose "Developer Default" setup type
   - Set root password (remember this for .env file)
   - Configure MySQL Server on port 3306 (default)
   - Start the MySQL service after installation

3. **Create Database**
   ```sql
   CREATE DATABASE insider_threat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. **Configure Environment Variables**
   - Copy `.env.example` to `.env`
   - Fill in your MySQL credentials:
     ```
     MYSQL_USER=root
     MYSQL_PASSWORD=your_mysql_password
     MYSQL_HOST=127.0.0.1
     MYSQL_PORT=3306
     MYSQL_DATABASE=insider_threat
     ```

### Option 2: Install MariaDB (MySQL-compatible)

1. **Install via winget**
   ```powershell
   winget install MariaDB.Server
   ```

2. **Start MariaDB Service**
   ```powershell
   net start mariadb
   ```

3. **Set Root Password**
   ```powershell
   mysql -u root -p
   ```
   Then run:
   ```sql
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'your_password';
   CREATE DATABASE insider_threat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. **Configure .env file** (same as above)

## How It Works

The application automatically:
1. Checks for MySQL connection using environment variables
2. Creates the database if it doesn't exist
3. Creates two tables:
   - `dataset_runs`: Stores metadata about each dataset upload
   - `analysis_results`: Stores analysis results with SHAP explanations
4. Stores uploaded datasets as tables named `activity_[run_id]`
5. Falls back to SQLite if MySQL is unavailable

## Database Schema

### dataset_runs
- `run_id` (UUID): Primary key
- `table_name` (VARCHAR): Name of the activity table
- `created_at` (DATETIME): Timestamp
- `row_count` (INTEGER): Number of rows in dataset

### analysis_results
- `run_id` (UUID): Foreign key to dataset_runs
- `created_at` (DATETIME): Timestamp
- `results_json` (JSON): Complete analysis results including identity_lookup

### Activity Tables
- Dynamically created for each dataset upload
- Named: `activity_[run_id_without_hyphens]`
- Contains the original dataset columns

## Testing MySQL Connection

After setup, restart the application:
```powershell
python app.py
```

The application will log whether it's using MySQL or SQLite in the console.

## Benefits of MySQL over SQLite

- **Concurrent access**: Multiple users can analyze data simultaneously
- **Scalability**: Handles larger datasets more efficiently
- **Persistence**: Centralized storage for historical analyses
- **Performance**: Better query performance for large datasets
- **Remote access**: Can be hosted on a separate server

## Troubleshooting

### Connection Refused
- Ensure MySQL service is running
- Check firewall settings
- Verify host and port in .env

### Authentication Failed
- Verify username and password in .env
- Check MySQL user permissions

### Database Creation Failed
- Ensure user has CREATE DATABASE permissions
- Check if database name already exists

## Current Status

The application currently uses SQLite as a fallback. Once MySQL is installed and configured, it will automatically switch to MySQL without any code changes.
