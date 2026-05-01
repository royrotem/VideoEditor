#!/usr/bin/env bash
# Quick smoke test against a running stack (`make dev`).
#
# Walks the happy path that the rest of the docs talk about:
#   1. /health/ready
#   2. create a project
#   3. upload an asset (ffmpeg generates a 5-second test clip)
#   4. open a chat session (requires ANTHROPIC_API_KEY)
#   5. submit a tiny EDL for rendering
#   6. fetch the presigned output URL
#
# Designed to fail loudly and early. Set SKIP_AGENT=1 to skip the
# steps that need ANTHROPIC_API_KEY.

set -euo pipefail

API="${API:-http://localhost:8000}"
SKIP_AGENT="${SKIP_AGENT:-0}"

say()   { printf '\033[1;34m[smoke]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[smoke]\033[0m %s\n' "$*" >&2; exit 1; }
have()  { command -v "$1" >/dev/null 2>&1; }

have curl   || fail "curl missing"
have jq     || fail "jq missing - install via brew/apt"
have ffmpeg || fail "ffmpeg missing"

# 1. Liveness ---------------------------------------------------------------

say "checking $API/health/ready ..."
ready=$(curl -fsS "$API/health/ready") || fail "backend not reachable"
echo "$ready" | jq .
echo "$ready" | jq -e '.status == "ok"' >/dev/null || fail "stack not ready"

# 2. Project ----------------------------------------------------------------

say "creating a project"
project=$(
  curl -fsS -X POST "$API/projects" \
       -H 'content-type: application/json' \
       -d '{"name":"smoke","description":"smoke test"}'
)
project_id=$(echo "$project" | jq -r .id)
say "  project_id=$project_id"

# 3. Asset upload -----------------------------------------------------------

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

clip="$tmp/clip.mp4"
say "generating a 5s test clip with ffmpeg ..."
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=teal:s=320x240:r=24:d=5" \
  -f lavfi -i "sine=frequency=440:duration=5" \
  -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac \
  -movflags +faststart "$clip"

say "uploading $clip"
upload=$(
  curl -fsS -X POST "$API/projects/$project_id/assets" \
       -F "file=@$clip;type=video/mp4"
)
asset_id=$(echo "$upload" | jq -r .asset.id)
duration=$(echo "$upload" | jq -r '.asset.size_bytes')
say "  asset_id=$asset_id (size=$duration bytes)"
say "  status=$(echo "$upload" | jq -r .asset.status)"

# 4. Chat session (optional) ------------------------------------------------

if [[ "$SKIP_AGENT" == "1" ]]; then
  say "SKIP_AGENT=1 - skipping chat + render steps"
  exit 0
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  say "ANTHROPIC_API_KEY unset - skipping chat + render steps"
  say "set it in .env (or export it) to exercise the agent path"
  exit 0
fi

say "opening a chat session"
session=$(
  curl -fsS -X POST "$API/projects/$project_id/sessions" \
       -H 'content-type: application/json' \
       -d '{"brief":"רוצה משהו קצר ואנרגטי, 5 שניות"}'
)
session_id=$(echo "$session" | jq -r .session.id)
say "  session_id=$session_id"
say "  director: $(echo "$session" | jq -r .assistant_message.content | head -c 120)..."

# 5. Submit a render --------------------------------------------------------

say "submitting a 1-clip EDL for rendering"
edl=$(jq -n \
  --arg aid "$asset_id" \
  '{
     edl: {
       version: 1,
       timeline: [{
         kind: "video",
         clips: [{
           clip: { asset_id: $aid, source_start_seconds: 0, source_end_seconds: 2 },
           timeline_start_seconds: 0,
           transition_in: "cut",
           transition_out: "cut"
         }]
       }],
       audio: { duck_music_under_voice: true, target_lufs: -14 },
       output: { width: 320, height: 240, fps: 24, container: "mp4" }
     },
     session_id: $session_id
   }')

job=$(curl -fsS -X POST "$API/projects/$project_id/render" \
           -H 'content-type: application/json' \
           -d "$edl")
job_id=$(echo "$job" | jq -r .id)
status=$(echo "$job" | jq -r .status)
say "  job_id=$job_id status=$status"

if [[ "$status" != "succeeded" ]]; then
  echo "$job" | jq .
  fail "render did not succeed"
fi

# 6. Output URL -------------------------------------------------------------

say "fetching presigned output URL"
url=$(curl -fsS "$API/render-jobs/$job_id/output-url" | jq -r .url)
say "  $url"

say "OK - end-to-end path works"
