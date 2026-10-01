<#
.SYNOPSIS
    Sobe a API (FastAPI/uvicorn) e a interface (Vite) ao mesmo tempo, num terminal só.

.DESCRIPTION
    Equivale a abrir dois terminais e rodar:

        .\.venv\Scripts\python.exe -m uvicorn leilao.api.main:app --reload --port 8000
        cd web; npm run dev

    A saída dos dois vem prefixada por [api] e [web]. Ctrl+C derruba os dois.
    Se um dos processos morrer sozinho, o outro é encerrado junto.

.EXAMPLE
    .\dev.ps1
    .\dev.ps1 -ApiPort 8001 -WebPort 5174
#>
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    # Não roda `npm install` mesmo que web/node_modules esteja faltando.
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

$root   = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$webDir = Join-Path $root 'web'

if (-not (Test-Path $python)) {
    throw "Virtualenv não encontrada em '$python'. Crie com: py -3.13 -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw "npm não encontrado no PATH. Instale o Node.js." }

if (-not $SkipInstall -and -not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Write-Host '[dev] web/node_modules ausente — rodando npm install...' -ForegroundColor Yellow
    Push-Location $webDir
    try { & $npm.Source install } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'npm install falhou.' }
}

# A API só libera CORS para http://localhost:5173 (ver api/main.py).
if ($WebPort -ne 5173) {
    Write-Host "[dev] Atenção: CORS da API está fixo em 5173; com -WebPort $WebPort o navegador vai bloquear as chamadas." -ForegroundColor Yellow
}

$procs = @()
$subs  = @()

function Start-Dev {
    param(
        [string]$Label,
        [string]$FilePath,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [System.ConsoleColor]$Color
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName               = $FilePath
    $psi.Arguments              = $Arguments
    $psi.WorkingDirectory       = $WorkingDirectory
    $psi.UseShellExecute        = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $proc.EnableRaisingEvents = $true

    $tag = [pscustomobject]@{ Label = $Label; Color = $Color }
    $sink = {
        if ($null -ne $EventArgs.Data) {
            Write-Host ("[{0}] {1}" -f $Event.MessageData.Label, $EventArgs.Data) `
                       -ForegroundColor $Event.MessageData.Color
        }
    }

    $script:subs += Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action $sink -MessageData $tag
    $script:subs += Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived  -Action $sink -MessageData $tag

    [void]$proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    return $proc
}

function Stop-Tree {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process -or $Process.HasExited) { return }
    # uvicorn --reload e npm.cmd criam netos; taskkill /T derruba a árvore inteira.
    & taskkill.exe /PID $Process.Id /T /F 2>&1 | Out-Null
}

try {
    Write-Host "[dev] API  -> http://localhost:$ApiPort  (docs em /docs)" -ForegroundColor DarkGray
    Write-Host "[dev] Web  -> http://localhost:$WebPort" -ForegroundColor DarkGray
    Write-Host "[dev] Ctrl+C encerra os dois." -ForegroundColor DarkGray

    $procs += Start-Dev -Label 'api' -Color Cyan -WorkingDirectory $root -FilePath $python `
                        -Arguments "-m uvicorn leilao.api.main:app --reload --port $ApiPort"

    $procs += Start-Dev -Label 'web' -Color Magenta -WorkingDirectory $webDir -FilePath $npm.Source `
                        -Arguments "run dev -- --port $WebPort --strictPort"

    # Enquanto os dois estiverem vivos, só repassa a saída (os handlers acima escrevem).
    while (-not ($procs | Where-Object { $_.HasExited })) {
        Start-Sleep -Milliseconds 200
    }

    $dead = $procs | Where-Object { $_.HasExited } | Select-Object -First 1
    Write-Host "[dev] um dos processos terminou (código $($dead.ExitCode)); encerrando o outro." -ForegroundColor Yellow
}
finally {
    foreach ($p in $procs) { Stop-Tree -Process $p }
    foreach ($s in $subs)  { Unregister-Event -SubscriptionId $s.Id -ErrorAction SilentlyContinue }
    Write-Host '[dev] encerrado.' -ForegroundColor DarkGray
}
