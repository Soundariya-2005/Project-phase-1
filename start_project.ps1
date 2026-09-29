$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$mysqlRoot = 'C:\Program Files\MySQL\MySQL Server 8.4'
$mysqlData = Join-Path $env:LOCALAPPDATA 'MySQL\InsiderThreat\data'
$mysqlExe = Join-Path $mysqlRoot 'bin\mysqld.exe'
$pythonExe = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path $mysqlExe) -or -not (Test-Path (Join-Path $mysqlData 'mysql.ibd'))) {
    throw 'MySQL server or its existing data directory is missing. The script will not initialize or overwrite database files.'
}
if (-not (Test-Path $pythonExe) -or -not (Test-Path (Join-Path $frontendRoot 'package.json'))) {
    throw 'Python or the React frontend is missing.'
}

foreach ($name in @('MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'User')
    if ($value) {
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}
if (-not $env:MYSQL_HOST) { $env:MYSQL_HOST = '127.0.0.1' }
if (-not $env:MYSQL_PORT) { $env:MYSQL_PORT = '3306' }
if (-not $env:MYSQL_DATABASE) { $env:MYSQL_DATABASE = 'insider_threat' }
if (-not $env:MYSQL_USER) { $env:MYSQL_USER = 'root' }
if (-not $env:MYSQL_PASSWORD) { throw 'The saved MYSQL_PASSWORD user environment variable is missing.' }

$mysqlListener = Get-NetTCPConnection -LocalPort ([int]$env:MYSQL_PORT) -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($mysqlListener) {
    $mysqlProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($mysqlListener.OwningProcess)"
    if ($mysqlProcess.Name -ne 'mysqld.exe') {
        throw "Port $($env:MYSQL_PORT) is occupied by another process; refusing to start MySQL."
    }
    Write-Host 'MySQL is already running.'
} else {
    Start-Process -FilePath $mysqlExe -WorkingDirectory $mysqlRoot -ArgumentList @(
        '--console',
        "--basedir=$mysqlRoot",
        "--datadir=$mysqlData",
        '--bind-address=127.0.0.1',
        '--mysqlx=OFF',
        "--port=$($env:MYSQL_PORT)"
    ) | Out-Null
    Write-Host 'MySQL is starting in its own window. Wait for "ready for connections" there.'
    Read-Host 'Press Enter here after MySQL reports ready'
}

$checkCode = @'
import app
from sqlalchemy import text
engine = app._database_engine()
if engine.dialect.name != "mysql":
    raise RuntimeError("MySQL is unavailable; refusing to start the project on the SQLite fallback.")
with engine.connect() as connection:
    connection.execute(text("SELECT 1"))
print("MySQL connection verified.")
'@
$checkCode | & $pythonExe -
if ($LASTEXITCODE -ne 0) {
    throw 'MySQL verification failed. Check the MySQL window and saved connection settings, then rerun this script.'
}

function Start-ProjectPowerShell {
    param(
        [string]$WorkingDirectory,
        [string]$CommandText
    )

    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($CommandText))
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $WorkingDirectory -ArgumentList @(
        '-NoExit', '-EncodedCommand', $encodedCommand
    ) | Out-Null
}

$backendListener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $backendListener) {
    $backendCommand = @'
Set-Location -LiteralPath '__PROJECT_ROOT__'
$runCode = @'
import app
engine = app._database_engine()
if engine.dialect.name != "mysql":
    raise RuntimeError("Refusing to launch Flask without MySQL.")
print("Flask verified MySQL; starting server.", flush=True)
app.app.run(debug=False, port=5000)
'@
$runCode | & '__PYTHON_EXE__' -u -
'@
    $backendCommand = $backendCommand.Replace('__PROJECT_ROOT__', $projectRoot).Replace('__PYTHON_EXE__', $pythonExe)
    Start-ProjectPowerShell -WorkingDirectory $projectRoot -CommandText $backendCommand
} else {
    Write-Host 'A backend is already listening on port 5000; leaving it running.'
}

$frontendListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $frontendListener) {
    $frontendCommand = "Set-Location -LiteralPath '$frontendRoot'; npm run dev -- --host 127.0.0.1"
    Start-ProjectPowerShell -WorkingDirectory $frontendRoot -CommandText $frontendCommand
} else {
    Write-Host 'A frontend is already listening on port 5173; leaving it running.'
}

Write-Host 'Project startup complete: http://127.0.0.1:5173/'