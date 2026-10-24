# ImaginePro online demo

The editor is deployed at https://imaginepro-demo.vercel.app. The Vercel project
is `imaginepro-demo` in `vptrciphers-projects`. The account's Vercel CLI session
publishes this project because the connected MCP session cannot access newly
created projects.

This is the PC renderer mode selected for the demo. Vercel serves the editor
and an authenticated API proxy. An isolated worker on this PC uses the existing
Codex ChatGPT login, FFmpeg, Whisper and the Canvas renderer. Keep the PC on,
awake, and connected to the internet. No video rendering runs inside a Vercel
request.

## Access and data

- The passcode is in `C:/Users/Noah/Downloads/ImaginePro-Online-Demo.txt`.
- Vercel stores the bridge credential and passcode as sensitive environment
  variables. They are not in the static JavaScript or this repository.
- The online worker uses `storage/cloud-demo/`, separately from the desktop
  app's database, uploads and private provider keys.
- The public tunnel rejects requests without a server credential or a
  short-lived signature for one media file. Signed file URLs expire in one hour.
- Media imports use 2 MiB chunks. Video playback and downloads use signed URLs
  to avoid routing large media bodies through a Vercel function.
- All demo visitors who have the passcode share this single demo workspace.
  This deployment does not provide separate user accounts.

## Running and publishing

`Start Online Demo.cmd` starts or reconnects the online renderer and opens the
deployed editor. It reuses an active connection. If the temporary tunnel has
stopped, it starts a new one, updates only this project's backend URL, and
publishes the current deployment package. The Vercel CLI must still be signed
in; its account credentials remain local to this PC.

The original `ImaginePro.exe` continues opening the local desktop editor.

To publish frontend changes:

1. In `frontend/`, run `npm run build`.
2. Run `.venv/Scripts/python.exe cloud/package_demo.py`.
3. Run `.venv/Scripts/python.exe cloud/configure_vercel.py` to refresh the
   project's environment variables from the encrypted local configuration.
4. From `storage/demo-deploy/package`, use the installed Vercel CLI:
   `node ../../../.tools/vercel/node_modules/vercel/dist/index.js deploy --prod --yes --project imaginepro-demo --scope team_2ooS5cJ2DIu0XGqE7LudXCrY --regions bom1`.

The deployment package contains only the static editor, login page and Node API
proxy. It excludes all footage, account credentials, backend files, local paths,
and worker databases. Do not deploy the repository root as a static site.

## Demo limits

The Cloudflare Quick Tunnel is temporary and has no production uptime guarantee.
Its hostname can change after restarting; the launcher republishes that change.
If the PC is offline, the editor reports that the renderer is unavailable.

Core generation uses Codex. Kiro and external API generation adapters remain
unimplemented, as in the local app. Enhance Director requires a working Pine
Labs AgenticOrg key configured in the online worker's Settings; the original
private key has not been copied to this workspace.

For independent cloud rendering and multiple users, replace the temporary
tunnel and local worker with durable compute, object storage, a job queue,
and individual accounts.
