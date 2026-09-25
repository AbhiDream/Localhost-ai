param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

# Stop the actual service workers only. Do not stop cmd.exe: when start.bat is
# double-clicked its own launcher command line contains this project path.
# Killing that parent command would terminate the batch before it opens either
# service window.
$root = ([System.IO.Path]::GetFullPath($ProjectRoot)).TrimEnd([char[]]@('\', '/'))
$owned = Get-CimInstance Win32_Process | Where-Object {
    $line = $_.CommandLine
    $line -and
    $line.IndexOf($root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    (
        ($_.Name -in @('python.exe', 'uvicorn.exe') -and $line -match 'backend.*uvicorn') -or
        ($_.Name -eq 'node.exe' -and $line -match 'frontend.*node_modules.*vite')
    )
}

$owned | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

