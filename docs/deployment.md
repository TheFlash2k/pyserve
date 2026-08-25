# Deployment

## TLS directly

Set both halves and pyserve serves HTTPS itself:

```bash
pyserve /srv/files --tls-cert cert.pem --tls-key key.pem --secure-cookie
```

```ini
TLS_CERT=/etc/letsencrypt/live/files.example.com/fullchain.pem
TLS_KEY=/etc/letsencrypt/live/files.example.com/privkey.pem
COOKIE_SECURE=true
```

Setting only one of the two is an error, caught at startup. Remember
`COOKIE_SECURE=true` whenever TLS is in play so the session cookie is never
sent in the clear.

## Behind a reverse proxy

Often easier, because the proxy already handles certificates, renewals and
HTTP/2. Bind pyserve to localhost so it is not reachable directly:

```ini
HOST=127.0.0.1
PORT=8000
COOKIE_SECURE=true
ACCESS_LOG=false
```

nginx:

```nginx
server {
    listen 443 ssl;
    server_name files.example.com;

    client_max_body_size 0;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
```

`client_max_body_size 0` and `proxy_request_buffering off` matter for uploads:
without them nginx buffers the whole file to disk first and enforces its own
one megabyte limit. Turning response buffering off keeps range requests
streaming rather than being materialised.

caddy:

```
files.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

pyserve does not read `X-Forwarded-For`, so its access log shows the proxy's
address. Use the proxy's log for client addresses, or turn pyserve's off with
`ACCESS_LOG=false`.

## systemd

```ini
[Unit]
Description=pyserve
After=network.target

[Service]
Type=simple
User=pyserve
Group=pyserve
ExecStart=/usr/local/bin/pyserve --config /etc/pyserve/pyserve.conf
Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/files
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
```

`ProtectSystem=strict` with a single `ReadWritePaths` is a good fit, because
pyserve writes nothing outside the directory it serves. Drop `ReadWritePaths`
entirely for a read only server.

Sessions live in memory, so a restart signs everyone out.

## Containers

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8000
ENTRYPOINT ["pyserve"]
CMD ["/data", "--host", "0.0.0.0"]
```

```bash
docker run --rm -p 8000:8000 -v /srv/files:/data:ro pyserve /data --read-only
```

Mounting the volume `:ro` and passing `--read-only` together is the right
pairing: the mount enforces it, and the flag makes the interface reflect it
rather than showing controls that fail with a storage error.

Configuration through the environment avoids mounting a config file:

```bash
docker run --rm -p 8000:8000 \
  -e PYSERVE_READ_ONLY=true \
  -e PYSERVE_AUTH_MODE=basic \
  -e PYSERVE_AUTH_USERS='alice:pbkdf2$240000$...' \
  -v /srv/files:/data:ro \
  pyserve /data
```

## Hardening checklist

**Bind narrowly.** `HOST=127.0.0.1` when a proxy sits in front. The default
`0.0.0.0` accepts from anywhere on the network.

**Run as a dedicated user** that owns only the directory being served.

**Do not run as root.** pyserve serves whatever the process can read. Combined
with `--follow-symlinks` and a link pointing at `/`, running as root would be a
very bad day. Symlinks are not followed by default for exactly this reason.

**Hide credentials with ignore rules.** Any secret inside the served tree
should be covered:

```gitignore
.env*
*.key
*.pem
id_rsa*
```

**Add a policy for the things that must never be served**, so it holds even if
someone edits the ignore file:

```ini
[iam]
deny * all *.key
deny * all *.pem
deny * all .env*
[end]
```

**Prefer read only.** If nobody needs to write, `READ_ONLY=true` removes the
whole write surface.

**Hash passwords.** `pyserve --hash-password` rather than a plain secret in a
file that gets committed or backed up.

**Set an upload ceiling.** `MAX_UPLOAD_MB` stops one client filling the disk.

**Think about search.** Regular expressions in the search box are evaluated
server side. On an exposed server, `ENABLE_SEARCH=false` or requiring
credentials is the control. See [Search](search.md).

**Watch the log.** IAM denials are logged at `warning` with the user, action
and path.

## Scale and limits

pyserve is a threaded standard library HTTP server. That suits a team, a lab, a
build artifact drop or a home network. It is not built to be a CDN.

- Each request takes a thread. Hundreds of concurrent downloads will not be
  efficient. Put a proxy in front, or use something else.
- Sessions are in memory, so multiple processes cannot share them. Run one
  process, or use `basic` auth, which is stateless.
- The directory cache is per process and rebuilds on every page load, which
  bounds how stale it can be but also means a very large tree is walked often.
  Tune `CACHE_THREADS` and `CACHE_MAX_DIRS`. See [The directory
  cache](cache.md).
