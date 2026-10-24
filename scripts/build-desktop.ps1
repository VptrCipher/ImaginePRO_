param([switch]$Shortcuts)
$ErrorActionPreference='Stop'
$studioRoot=Split-Path -Parent $PSScriptRoot
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if(-not(Test-Path -LiteralPath $compiler)){$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'}
if(-not(Test-Path -LiteralPath $compiler)){throw 'The Windows .NET Framework C# compiler is unavailable.'}
$executable=Join-Path $studioRoot 'ImaginePro.exe'
$icon=Join-Path $studioRoot 'desktop\ImaginePro.ico'
$source=Join-Path $studioRoot 'desktop\ImagineProLauncher.cs'
& $compiler '/nologo' '/target:winexe' '/optimize+' '/reference:System.dll' '/reference:System.Core.dll' '/reference:System.Drawing.dll' '/reference:System.Windows.Forms.dll' '/reference:System.Net.Http.dll' '/reference:System.Web.Extensions.dll' "/win32icon:$icon" "/out:$executable" $source
if($LASTEXITCODE -ne 0){throw 'ImaginePro launcher compilation failed.'}
Write-Host "Built $executable"
if($Shortcuts){
    $desktopFolder=[Environment]::GetFolderPath('Desktop')
    $programsFolder=Join-Path ([Environment]::GetFolderPath('Programs')) 'ImaginePro'
    New-Item -ItemType Directory -Path $programsFolder -Force | Out-Null
    $shortcutShell=New-Object -ComObject WScript.Shell
    foreach($shortcutPath in @((Join-Path $desktopFolder 'ImaginePro.lnk'),(Join-Path $programsFolder 'ImaginePro.lnk'))){
        if(Test-Path -LiteralPath $shortcutPath){
            $prior=$shortcutShell.CreateShortcut($shortcutPath)
            if($prior.TargetPath -and $prior.TargetPath -ne $executable){
                $shortcutPath=Join-Path (Split-Path -Parent $shortcutPath) 'ImaginePro Local.lnk'
            }
        }
        $shortcut=$shortcutShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath=$executable
        $shortcut.WorkingDirectory=$studioRoot
        $shortcut.IconLocation="$executable,0"
        $shortcut.Description='Open ImaginePro with your connected Codex account'
        $shortcut.Save()
        Write-Host "Created $shortcutPath"
    }
}
