<#
    .SYNOPSIS
    Installs analyzer.exe

    .DESCRIPTION
    Installs analyzer.exe

    .PARAMETER OutputDir
    The directory where analyzer.exe will be installed. If not specified, the default is $HOME\.analyzer

    .INPUTS
    None.

    .OUTPUTS
    None.

    .EXAMPLE
    PS> install.ps1 -OutputDir "${env:USERPROFILE}\AppData\Local\analyzer_gui\cli"

    .LINK
    Online version: https://github.com/elfys/analyzer
#>

param (
    [string]$OutputDir = "${env:USERPROFILE}\.analyzer"
)

Function Main() {
    if (Test-Path -Path $OutputDir) {
      Remove-Item -Path $OutputDir -Recurse -Force
    }

    New-Item -Path $OutputDir -ItemType Directory

    $Response = Invoke-RestMethod -Uri https://api.github.com/repos/elfys/analyzer/releases/latest
    $DownloadURL = $Response.assets[0].browser_download_url

    $DownloadPath = "${env:USERPROFILE}\AppData\Local\Temp\analyzer.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $DownloadURL -OutFile $DownloadPath
    Expand-Archive -Path $DownloadPath -DestinationPath $OutputDir

    # Update env vars

    $PathParts = [System.Environment]::GetEnvironmentVariable('PATH', "User") -Split ";"

    # Remove existing paths, so we don't add duplicates
    $NewPathParts = $PathParts.Where{ $_ -ne $OutputDir }
    $NewPathParts = $NewPathParts + $OutputDir
    $NewPath = $NewPathParts -Join ";"
    [System.Environment]::SetEnvironmentVariable('PATH', $NewPath, "User")


    Write-Host "analyzer.exe is successfully installed. You may need to close and reopen your terminal before using it."
}

Main
