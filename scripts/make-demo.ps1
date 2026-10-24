$ErrorActionPreference = 'Stop'
$editorRoot = Split-Path -Parent $PSScriptRoot
$fixtureDirectory = Join-Path $editorRoot '.fixtures'
New-Item -ItemType Directory -Force -Path $fixtureDirectory | Out-Null
Add-Type -AssemblyName System.Speech
$demoVoice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$demoVoice.SetOutputToWaveFile((Join-Path $fixtureDirectory 'speech.wav'))
$demoPrompt = New-Object System.Speech.Synthesis.PromptBuilder
$demoPrompt.AppendText('Welcome to the local video studio.')
$demoPrompt.AppendBreak([TimeSpan]::FromSeconds(1.8))
$demoPrompt.AppendText('Um, today we are turning raw footage into a polished video.')
$demoPrompt.AppendBreak([TimeSpan]::FromSeconds(1.5))
$demoPrompt.AppendText('Add clean captions, make the cuts, and share your story.')
$demoVoice.Speak($demoPrompt)
$demoVoice.Dispose()
Write-Host 'Generated a synthetic speech fixture. Run scripts/acceptance_demo.py with the backend running.'
