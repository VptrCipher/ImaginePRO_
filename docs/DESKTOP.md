# ImaginePro one-click Windows launcher

Double-click **ImaginePro** on the Windows desktop or open it from **Start → ImaginePro**. The same native launcher is at `ImaginePro.exe` in the application folder. It opens the existing web editor in the default browser after checking the server, installed rendering dependencies and supported Codex ChatGPT sign-in. A terminal window is not required.

This is a launcher for the installation on this computer. Keep `C:\AI Builder\video-editor` in place; the executable uses its adjacent application files, Python environment, Node rendering engine, installed FFmpeg/browser and Codex CLI. It is not a portable installer for another computer. Desktop and Start menu shortcuts reference the application folder. On this machine Windows redirects Desktop to `C:\Users\Noah\OneDrive\Desktop`.

Closing the browser does not interrupt a running generation. The local server stays in the background until Windows exits or the owned server process is stopped. Reopening the shortcut reuses that server; repeated launches do not reset the database or start a second worker. Startup uses a per-installation mutex and checks the server identity before reuse. An unrelated service occupying port 8765 is reported without being terminated.

## Data and account

Existing SQLite projects, imported media, generated outputs, style profiles and DPAPI-encrypted AgenticOrg credentials remain under the same `storage/` directory. No project migration or credential copying is performed. The packaging backup and original record snapshot are in `storage/backups/one-click-20261024-165423/`.

Codex runs through its supported installed CLI and existing account login. The launcher checks that connection before opening the editor. If sign-in expires, its **Sign in to Codex** button opens the official interactive `codex login` flow, then **Try again** repeats the check. The launcher does not read or embed Codex credentials.

Executable discovery works without a developer terminal's PATH: Codex is found in the installed app's current binary directory, Node in its installed directory, FFmpeg via PATH or the existing WinGet package, and animation rendering through installed Chrome/Edge. Windows speech synthesis also finds the system PowerShell installation directly when needed. No programs, models or dependencies are downloaded during normal startup.

## Diagnostics and rebuild

- `storage/logs/launcher.log`: startup results and safe errors.
- `storage/logs/server.log`: background server diagnostics.
- `storage/desktop/last-launch.json`: last launch result, whether a server was started/reused and Codex connection status.
- `storage/desktop/server.json`: owned background server PID and start time.
- `storage/desktop/generation-verification.json`: real Codex → narration/transcription → original animation → verified 1080p output → saved timeline, exercised through the background server.

Rebuild with `scripts/build-desktop.ps1 -Shortcuts` using Windows' existing .NET Framework C# compiler. No downloaded build system is required. The native source is `desktop/ImagineProLauncher.cs`; `desktop/server.pyw` redirects Python's windowless standard streams to the server log before importing Uvicorn. The icon extends the existing ImaginePro mark.

For automated checks, `ImaginePro.exe --no-browser` starts/reuses the server and checks Codex without opening a browser; `ImaginePro.exe --check` checks an already-running server. Both return a nonzero exit status on failure and write the diagnostic receipt. Development setup/foreground operation remains available through `scripts/start.ps1`; passing `-Install` or `-Build` to the older CMD launcher preserves that workflow.
