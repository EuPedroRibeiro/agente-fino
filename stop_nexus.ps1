$ErrorActionPreference = "Stop"
$connections = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if ($process.CommandLine -like "*python*main.py*") {
        Stop-Process -Id $connection.OwningProcess -Force
        Write-Host "NexusTI AI parado: PID $($connection.OwningProcess)"
    }
}
