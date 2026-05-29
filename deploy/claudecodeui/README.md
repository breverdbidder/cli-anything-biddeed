# Claude Code Phone Dashboard — claudecodeui (CloudCLI) deploy bundle

Stand up a web dashboard that shows **all your Claude Code sessions on one host**, usable from your phone's browser, with push notifications when a session needs attention.

## What this is (and isn't)

- **Is:** a phone-friendly wall for the `claude` sessions running on the host you install it on. Run several sessions on that box (tmux panes or `claude --worktree` per task) and see/control every one from your phone.
- **Isn't:** a view of your GHA-dispatched ephemeral runners. Those have no persistent process to attach to — your Supabase mission-control is the right surface for the autonomous fleet. Deploy this for interactive/persistent work.

Picked over `happy` (native app, heavier, needs app install) and `octogent` (great monitoring model but source-only, less mature) because it's web-based — zero app-store friction, just a URL on your phone — and the freshest of the three (last commit the day we evaluated). License is AGPL-3.0, fine for self-use.

## Files

| File | Purpose |
|---|---|
| `bootstrap.sh` | One-shot install on the host: Node 22, clone, build, systemd service |
| `claudecodeui.service` | systemd unit (templated on the run user, so it sees that user's `~/.claude`) |
| `.env` | Server config — port 3001, auth DB path, optional `CLAUDE_CLI_PATH` |
| `cloudflared-config.yml` | HTTPS tunnel so the phone can reach it (required for push + PWA) |

## Deploy (on the Hetzner box, as the user who runs `claude`)

```bash
sudo RUN_AS_USER=ariel ./bootstrap.sh
curl -sI http://127.0.0.1:3001 | head -1     # expect HTTP/1.1 200
```

The service runs as `claudecodeui@ariel` and auto-discovers projects/sessions from `/home/ariel/.claude`. First load, create your login in the UI (credentials live in the SQLite auth DB at `/opt/claudecodeui-data/auth.db`).

## Reach it from your phone (HTTPS, no open ports)

```bash
# one-time
cloudflared tunnel login
cloudflared tunnel create cc-dashboard
# put cloudflared-config.yml at /etc/cloudflared/config.yml, fill <TUNNEL_UUID> + your hostname
cloudflared tunnel route dns cc-dashboard cc.yourdomain.com
sudo cloudflared service install
```

Then on your phone open `https://cc.yourdomain.com`, log in, and **Add to Home Screen** to install it as a PWA and enable push.

**Harden it:** gate the hostname behind **Cloudflare Access** (email/OTP or your IdP) so only you can reach the login page. A dashboard that can drive `claude` on your box should never sit on the open internet behind just an app password.

### Private alternative — Tailscale
If you'd rather keep it off the public internet entirely: `tailscale up` on the box and phone, then `tailscale serve https / http://127.0.0.1:3001`. Gives HTTPS on your tailnet (push works), reachable only from your devices.

## Run sessions to actually see on it

```bash
# On the box, start a few parallel sessions in their own worktrees:
cd ~/projects/biddeed && claude --worktree feature-x
cd ~/projects/zonewise && claude --worktree zoning-sync
# ...each appears as a session in the dashboard, controllable from your phone.
```

## Notes
- node-pty compiles native — `build-essential` + `python3` are installed by bootstrap.
- The auth DB also stores GitHub tokens you add in-UI; keep `/opt/claudecodeui-data` on persistent disk and backed up.
- To update: re-run `bootstrap.sh` (it does `git pull --ff-only` + rebuild + restart).
