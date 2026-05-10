# Reverse Proxy Beta Templates

These templates add a proxy-layer guard in front of a local Lattice runtime.

They are intentionally broader than the app's internal boundary:

- keep `/health` open for a simple probe
- require IP allowlist plus HTTP Basic auth for everything else
- forward `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto` to the FastAPI app

Use these when you want one more layer outside the app for a hosted private beta.

## Included Templates

- `caddy/Caddyfile.example`
- `nginx/lattice-beta.conf.example`

## Pair With App Env

At the app layer, still set:

- `LATTICE_API_KEY`
- `LATTICE_BETA_PASSWORD`
- `LATTICE_ALLOWED_HOSTS`
- `LATTICE_TRUSTED_PROXY_IPS`

Optional app-layer duplication:

- `LATTICE_BETA_ALLOWED_IPS`

If the proxy runs on the same host as the app, `LATTICE_TRUSTED_PROXY_IPS=127.0.0.1` is usually enough.

## Notes

- Replace example hostnames, IPs, and credentials before use.
- The Caddy template expects a bcrypt password hash.
- The nginx template expects an htpasswd file path.
- Both templates assume the app listens on `127.0.0.1:8000`.
