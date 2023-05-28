<#
    .SYNOPSIS
    Installs analyzer.exe

    .DESCRIPTION
    Installs analyzer.exe to $HOME\.pyenv

    .INPUTS
    None.

    .OUTPUTS
    None.

    .EXAMPLE
    PS> install.ps1

    .LINK
    Online version: https://github.com/elfys/analyzer
#>

$AnalyzerDir = "${env:USERPROFILE}\.analyzer"
$LegacyAnalyzerDir = "${env:USERPROFILE}\.analyzing"

Function Main() {
    if (Test-Path -Path $LegacyAnalyzerDir) {
      Remove-Item -Path $LegacyAnalyzerDir -Recurse -Force
    }
    if (Test-Path -Path $AnalyzerDir) {
      Remove-Item -Path $AnalyzerDir -Recurse -Force
    }

    New-Item -Path $AnalyzerDir -ItemType Directory

    $DownloadPath = "$AnalyzerDir\analyzer.zip"

    $Response = Invoke-RestMethod -Uri https://api.github.com/repos/elfys/analyzer/releases/latest
    $DownloadURL = $Response.assets[0].browser_download_url

    Invoke-WebRequest -UseBasicParsing -Uri $DownloadURL -OutFile $DownloadPath
    Expand-Archive -Path $DownloadPath -DestinationPath $AnalyzerDir
    Remove-Item -Path $DownloadPath

    # Update env vars

    $PathParts = [System.Environment]::GetEnvironmentVariable('PATH', "User") -Split ";"

    # Remove existing paths, so we don't add duplicates
    $NewPathParts = $PathParts.Where{ $_ -ne $AnalyzerDir }
    $NewPathParts = $NewPathParts + $AnalyzerDir
    $NewPath = $NewPathParts -Join ";"
    [System.Environment]::SetEnvironmentVariable('PATH', $NewPath, "User")


    Write-Host "analyzer.exe is successfully installed. You may need to close and reopen your terminal before using it."
}

Main
