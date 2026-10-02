# InterviewCopilot MVP release notes

The supported live-listening target is the Windows Electron app. Fresh profiles
default to system audio enabled and microphone disabled. Existing saved audio
preferences are preserved. System loopback captures computer playback, including
notifications and music; it does not identify an individual speaker.

## Implemented behavior

- Audio capture fails visibly when system audio cannot start, rather than silently
  switching to the microphone. Device disconnection stops listening.
- Reconnects use refreshed credentials, heartbeat checks and a bounded five-second
  audio buffer. If the connection stays down longer, the app reports missed audio.
  Audio already sent on a broken connection cannot be guaranteed to survive.
- Questions are processed in order through a bounded queue. Long utterances are
  transcribed in pieces and combined before answering. Silence has a 650 ms
  endpoint threshold; this is not continuous streaming speech recognition.
- AI answers have request IDs, provider labels, saved responses and first-token
  latency measurements. Provider failures before the first token can fall back;
  mid-answer failures are shown and require repeating the question.
- Session end waits for queued processing before completing the session and
  requesting feedback. Interviewer-only feedback evaluates sample answers and
  explicitly cannot assess the candidate's actual performance.
- Packaged resources use a secure app protocol and hash routing. Overlay state is
  restored after closing and reopening it.
- App startup has no external font or payment-script dependency. The payment
  script loads on checkout with a timeout and visible failure handling.
- WebSocket authentication is sent in the first message, outside the URL. Session,
  transcript and feedback access require ownership. Refresh rotation is atomic;
  logout revokes the server refresh credential.

## Build and run

Install frontend and Electron dependencies with `npm ci` in their directories.
From `electron/`, run `npm run build:win`. It builds the frontend and Electron,
then produces a local installer in `electron/release/` without publishing.

For a hosted backend, set `VITE_API_URL=https://your-api-host/api/v1` in the build
environment before building the installer. The default URL is localhost for local
development. No API credentials belong in the frontend build.

Copy `backend/.env.example` to `backend/.env` and configure valid RSA keys,
provider keys/models, storage and Razorpay settings. For production set
`ENV=production`, `DEBUG=false`, and include `app://interviewcopilot` in
`CORS_ORIGINS` along with any deployed web frontend origin. Production refresh
cookies require HTTPS and use HttpOnly, Secure and SameSite=None; refresh/logout
reject untrusted Origin headers.

Copy `infra/.env.example` to `infra/.env` and configure a generated alphanumeric
database password. Compose still has development defaults; production startup
rejects the default password. Existing database volumes keep their old password;
changing the env file alone does not rotate it.

Supply `infra/nginx/ssl/cert.pem` and `key.pem`, and set Nginx's server name to
the actual API hostname. From `infra/`, run:

```sh
docker compose up -d db redis
docker compose --profile migrate run --rm alembic
docker compose up -d backend nginx
```

PostgreSQL and Redis have no published host ports. The backend's direct port is
bound to localhost; public traffic goes through Nginx. `/health` is liveness;
`/ready` checks database and Redis availability and drives the container check.

## Verification and remaining release checks

Automated tests isolate databases and providers; they do not measure real API
latency. The desktop smoke test uses synthetic overlay messages and never starts
audio. Run it against a local packaged app launched with
`--remote-debugging-port=9227`, then `node --experimental-websocket tests/desktop-smoke.cjs` in `electron/` (Node 20).
Do not enable remote debugging for a distributed release.

Verified locally: 47 backend tests pass, frontend production build and Electron
TypeScript build pass, Compose configuration validates, Windows NSIS installer
build succeeds, and the packaged desktop smoke test passes for UI loading,
preload access, overlay routing, streamed text, and restored answer after reopen.
The test shell explicitly sets `DEBUG=false` because its inherited DEBUG value
is not a boolean. The local signing-tool cache excluded unused macOS symlinks
to work around this Windows account's symlink restrictions; no publisher signing
certificate was supplied.

Before distributing, verify microphone-off system capture in actual Zoom, Meet
and Teams calls, including headphones, low volume, long questions, output-device
changes and network loss. Measure the interval from the end of a spoken question
to the first visible answer using the configured providers. Confirm HTTPS login
and refresh after the access token expires, and resume/payment flows with the
configured services. Code signing requires a publisher certificate; local builds
without one are unsigned. This repository does not claim these external checks
or a signed release have been completed.
