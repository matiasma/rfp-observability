<#
.SYNOPSIS
  Instala a skill "analise-rfp-observabilidade" para uso pessoal no GitHub Copilot e registra RFP_KIT_HOME.
.EXAMPLE
  .\scripts\instalar-skill.ps1
#>
param(
    [string]$Destino = (Join-Path $HOME ".copilot\skills\analise-rfp-observabilidade")
)

$kit = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$origem = Join-Path $kit ".github\skills\analise-rfp-observabilidade"

New-Item -ItemType Directory -Force -Path $Destino | Out-Null
Copy-Item -Path (Join-Path $origem "*") -Destination $Destino -Recurse -Force
[Environment]::SetEnvironmentVariable("RFP_KIT_HOME", $kit, "User")

Write-Host "Skill instalada em: $Destino"
Write-Host "RFP_KIT_HOME = $kit (variável de usuário — reabra o terminal/VS Code)"
Write-Host "Dependências: python -m pip install -r `"$kit\requirements.txt`""
