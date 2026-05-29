# claudecodeui phone dashboard — DEPLOYED 2026-05-29

STATUS: LIVE on the Hetzner box. systemd unit `claudecodeui@root` active; HTTP 200 on 127.0.0.1:3001.
Build: @cloudcli-ai/cloudcli v1.32.0. Deploy run: actions/runs/26661093580 (success).

## Corrections to the original handoff (so the next session does not relearn this)
1. DISPATCH PRIMITIVE: do NOT insert a summit_chat_dispatch row with target_workflow to fire a
   workflow. chat_bypass_auto_consumer routes ONLY on dispatch_inputs->>'kind'
   (noop | supabase_sql | pg_net_request | gh_push_files | quarantine_self) and quarantines
   everything else as unknown_kind. To fire a GitHub workflow from SQL, call:
     SELECT public.fire_workflow_dispatch(p_repo, p_workflow_file, p_ref, p_inputs jsonb);
   It reads vault.everest_gh_pat and POSTs to the Actions API (http 204 = dispatched).
   Read results back via the Actions API using the same PAT (runs -> jobs -> job logs 302 -> blob URL).
2. hetzner-run.yml workflow_dispatch input field = `command` (required, default 'docker ps').
   It SSHes root@HETZNER_IP, runs the command, tails the output to Telegram.
3. RUN_AS_USER must be `root`, NOT `ariel`. There is no `ariel` user on the box; claude + its
   sessions live under root (~/.claude). bootstrap chowned ariel:ariel and died -> use root.
4. bootstrap.sh bug: it `cp`s `.env` but the bundle ships only `.env.example`. Pre-seed
   /opt/claudecodeui/.env from deploy/claudecodeui/.env.example before running bootstrap.

## Remaining (manual, one-time): expose to phone over HTTPS
cloudflared is installed on the box. The only non-automatable step is the browser OAuth:
  cloudflared tunnel login
  cloudflared tunnel create cc-dashboard
  cp /opt/cli-anything-biddeed/deploy/claudecodeui/cloudflared-config.yml /etc/cloudflared/config.yml   # fill <TUNNEL_UUID> + hostname
  cloudflared tunnel route dns cc-dashboard cc.biddeed.ai
  sudo cloudflared service install
Then phone -> https://cc.biddeed.ai -> log in -> Add to Home Screen. Gate behind Cloudflare Access.
Private alternative: tailscale up (box+phone) then `tailscale serve https / http://127.0.0.1:3001`.
