# Pass 104 — Platform IAM/session foundation

## Syfte

Ersätta den miljövariabelbaserade identiteten som enda servermekanism med en första
riktig inloggnings- och sessionsgrund, utan att låsa Crow Platform till en extern
identity provider innan den integrationsgränsen är beslutad.

## Scope

- Lokal filbaserad användarpost under `config/users/` som bootstrap-lager.
- Lösenord lagras aldrig i klartext; scrypt med unik salt används.
- Signerad, tidsbegränsad HTTP-only sessionscookie med HMAC-SHA256.
- `POST /api/auth/login`, `POST /api/auth/logout` och `GET /api/auth/me`.
- `/` visar inloggningssidan när `CROW_AUTH_MODE=session` och ingen giltig session finns.
- Inloggad kund styrs till `/app`; `platform-admin` styrs till `/admin`.
- Entitlement- och admin-API:er använder request/session-identitet.
- Befintlig environment-identitet finns kvar som kompatibilitetsläge under övergången.
- `crow-user` skapar bootstrap-användare utan att lösenord läggs i shell history.

## Säkerhetsgräns

Session mode kräver `CROW_SESSION_SECRET` med minst 32 tecken. Cookie är Secure som
standard och kan endast sänkas med `CROW_COOKIE_SECURE=false` för lokal HTTP-testning.
Ogiltig eller utgången signatur ger ingen identitet. Admin-API:er fortsätter kräva
rollen `platform-admin`.

Detta är ett lokalt IAM-bootstrap-lager, inte slutlig enterprise identity. OIDC/SAML,
MFA, password reset, rate limiting, lockout, audit-logg för login och central
användarlivscykel ligger utanför detta pass.

## Deployment

För session mode behövs minst:

```text
CROW_AUTH_MODE=session
CROW_SESSION_SECRET=<minst 32 slumpmässiga tecken>
CROW_COOKIE_SECURE=false   # endast så länge servern kör HTTP på internt LAN
```

Skapa första administratören exempelvis med:

```bash
crow-user admin --customer crow-admin --role platform-admin \
  --config-root /srv/crow-data/platform/config
```

CLI frågar interaktivt efter lösenord och bekräftelse.

## Acceptance

- Oinloggad session-mode visar login-yta.
- Korrekt kundlogin skapar session och ger `/app` som destination.
- Adminlogin ger `/admin` och tillgång till admin-API.
- Fel lösenord skapar inte session.
- Befintligt environment-läge fortsätter fungera under migrationsperioden.
- Ruff format/check, mypy strict, pytest, architecture review och build är CI-gate.
