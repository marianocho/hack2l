# docker-up.ps1 -- sobe o Docker Desktop nesta maquina, contornando os sockets
# orfaos ANTES do boot em vez de reagir ao erro.
#
# POR QUE ISTO EXISTE
#
# O Docker Desktop 4.85.0 nesta maquina deixa arquivos de socket orfaos de ZERO
# BYTE ao parar. No boot seguinte ele tenta remove-los para recriar, o Windows
# recusa ("the file cannot be accessed by the system"), e ele aborta. Nem
# Remove-Item -Force nem Rename-Item funcionam no ARQUIVO -- so renomear a
# PASTA PAI.
#
# Sao DOIS, em pastas diferentes, e e' por isso que a receita antiga so durava
# um boot: ela renomeava so a primeira, destravava o Inference manager, e o
# Secrets Engine morria no socket dele, na segunda pasta.
#
#   C:\Users\luisf\AppData\Local\Docker\run\dockerInference
#   C:\Users\luisf\AppData\Local\docker-secrets-engine\engine.sock
#
# Medido em 11/08: com as duas renomeadas o daemon subiu em ~10s. E os orfaos
# VOLTAM a cada parada -- por isso isto roda antes de todo boot, e nao so
# quando da erro.
#
# NAO E' DNS, NAO E' REDE. E' criacao de arquivo de socket local, antes de
# qualquer rede existir.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\docker-up.ps1
#   ... -Limpar            apaga tambem as pastas .old-* acumuladas
#   ... -Timeout 300       segundos de espera pelo daemon (padrao 180)

param(
    [switch]$Limpar,
    [int]$Timeout = 180
)

$ErrorActionPreference = "Stop"

$Pastas = @(
    "C:\Users\luisf\AppData\Local\Docker\run",
    "C:\Users\luisf\AppData\Local\docker-secrets-engine"
)
$DockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

function Daemon-Responde {
    try {
        $null = & docker version --format '{{.Server.Version}}' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Limpa-Velhas {
    $velhas = @()
    foreach ($d in $Pastas) {
        $pai = Split-Path $d -Parent
        $folha = Split-Path $d -Leaf
        if (Test-Path $pai) {
            $velhas += Get-ChildItem $pai -Directory -Filter "$folha.old-*" -ErrorAction SilentlyContinue
        }
    }
    if ($velhas.Count -eq 0) { return }
    if (-not $Limpar) {
        Write-Host "  ($($velhas.Count) pasta(s) .old-* acumulada(s); -Limpar tenta apagar)"
        return
    }
    $apagadas = 0; $presas = 0
    foreach ($v in $velhas) {
        try {
            Remove-Item $v.FullName -Recurse -Force -ErrorAction Stop
            Write-Host "  apagada   $($v.Name)"; $apagadas++
        } catch { $presas++ }
    }
    if ($presas -gt 0) {
        # Testado em 11/08: Remove-Item, `cmd rd /s /q`, caminho estendido
        # \\?\ e `del /f` falham TODOS com "nao e' possivel o acesso ao arquivo
        # pelo sistema". E' a mesma causa raiz do problema original -- socket
        # AF_UNIX cujo objeto de respaldo sumiu; o Windows nao abre o arquivo,
        # entao nao apaga, entao a pasta nao sai.
        Write-Host "  $presas pasta(s) presa(s): o Windows nao consegue apagar os"
        Write-Host "  sockets mortos la dentro (mesma causa do bug original)."
        Write-Host "  Ocupam ZERO byte -- e' sujeira visual, nao problema. Some"
        Write-Host "  de vez com um reboot, se incomodar."
    }
}

# 1. Idempotente. Reiniciar um Docker saudavel derruba containers de graca.
#
# ⚠️ A limpeza roda ANTES desta saida, e de proposito: na primeira versao ela
# vinha depois, entao `-Limpar` nao fazia nada com o daemon no ar -- que e'
# justamente quando se quer limpar sem mexer em nada. Era o padrao de bug do
# projeto outra vez: guarda condicionada ao mesmo sinal do qual nao deveria
# depender. Ver "O PADRAO DE BUG DESTE PROJETO" no CLAUDE.md.
if ($Limpar) { Limpa-Velhas }

if (Daemon-Responde) {
    $v = & docker version --format '{{.Server.Version}}' 2>$null
    Write-Host "daemon ja esta no ar (Server $v). Nada a fazer."
    exit 0
}

Write-Host "daemon fora. Aplicando a receita das DUAS pastas..."

# 2. Nenhum processo pode estar segurando os sockets.
$procs = Get-Process | Where-Object { $_.Name -match 'docker' }
if ($procs) {
    Write-Host "  parando: $(($procs | Select-Object -ExpandProperty Name -Unique) -join ', ')"
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 4
}

# 3. Renomear as pastas pai. O arquivo em si o Windows nao deixa tocar.
$ts = Get-Date -Format HHmmss
foreach ($d in $Pastas) {
    if (-not (Test-Path $d)) { Write-Host "  ausente   $d"; continue }
    $novo = (Split-Path $d -Leaf) + ".old-$ts"
    try {
        Rename-Item -LiteralPath $d -NewName $novo -ErrorAction Stop
        Write-Host "  renomeada $d -> $novo"
    } catch {
        Write-Host "  FALHOU    $d : $($_.Exception.Message)"
    }
}

# 4. As .old-* se acumulam. So contamos -- apagar e' decisao de quem roda.
#    (Com -Limpar, as que ja existiam foram apagadas la em cima; esta chamada
#    pega as que acabaram de ser criadas nesta execucao.)
Limpa-Velhas

# 5. Subir e esperar de verdade -- "iniciado" nao e' "no ar".
if (-not (Test-Path $DockerExe)) { Write-Error "nao achei $DockerExe"; exit 1 }
Start-Process $DockerExe
Write-Host "  Docker Desktop iniciado, aguardando o daemon..."

$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
    if (Daemon-Responde) {
        $s = [int]((Get-Date) - $t0).TotalSeconds
        $v = & docker version --format '{{.Server.Version}}' 2>$null
        Write-Host "daemon no ar em ${s}s (Server $v)."
        exit 0
    }
    Start-Sleep 5
}

Write-Host "daemon NAO respondeu em ${Timeout}s."
Write-Host "Veja o erro exato e o caminho do socket em:"
Write-Host "  C:\Users\luisf\AppData\Local\Docker\log\host\com.docker.backend.exe.log"
Write-Host "A mensagem tem a forma:"
Write-Host "  initializing <Componente>: listening on unix://<CAMINHO>: remove <CAMINHO>"
Write-Host "Se o <CAMINHO> nao estiver nas duas pastas conhecidas, acrescente a `$Pastas."
exit 1
