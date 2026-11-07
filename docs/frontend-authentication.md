# Frontend authentication

## Routes

- `/login` submits to `POST /api/v1/auth/login`.
- `/register` submits to `POST /api/v1/auth/register`.
- Both routes save the returned bearer token and profile data in `sessionStorage` and navigate to `/`.

## API configuration

Set `NEXT_PUBLIC_API_BASE_URL` to the base URL of the FastAPI service, without `/api/v1`.
For local development, copy `frontend/.env.example` to `frontend/.env.local` and use
`http://127.0.0.1:8000`.

For production, set the variable in the frontend hosting dashboard to the deployed API's HTTPS origin.
The backend reads `CORS_ORIGINS` as a comma-separated list; add the deployed Vercel origin there before browser requests can succeed. The default permits local development origins.

## Security and current limitations

This is an initial integration with the existing bearer-token API. The token is stored in
browser `sessionStorage`, so it is scoped to the current tab session but remains accessible
to JavaScript. Before production launch, review the authentication architecture and prefer
Secure, HttpOnly cookies or another reviewed session approach, alongside CSRF protections
where applicable. The dashboard is not yet protected by an authentication gate and does not
yet fetch real dashboard data.


## Dashboard access gate

The dashboard now checks for a session token and verifies it with `GET /api/v1/auth/me`.
If the token is missing or invalid, it redirects to `/login`. It displays the signed-in user's name
and the organization information returned at sign-in, and provides a sign-out action.

This is a client-side user-experience gate, not a substitute for backend authorization. Every
business-data endpoint must independently validate the bearer token and enforce organization
membership. The dashboard's metrics and social account cards are still sample data.

## Workspaces on the dashboard

After `GET /api/v1/auth/me` succeeds, the dashboard calls `GET /api/v1/organizations` and shows the
workspace name and role from that server response instead of only the values saved at sign-in. The
active workspace id is kept in `sessionStorage`; if it is not in the server's list, the first
workspace is used. The workspace button opens a dropdown listing every workspace, with a "New workspace" form that calls
`POST /api/v1/organizations` and switches to the new workspace. The metrics and social account cards are still sample data.

The "API endpoint" developer line on the login and register pages is hidden when the frontend is
built for production.

## Sign-out, password change and password reset

- Sign out (dashboard) calls `POST /auth/logout` to revoke the token on the server, then clears `sessionStorage`. If the server cannot be reached, the local session is still cleared.
- `/forgot-password` requests a reset email; the reply is the same for every address.
- `/reset-password` reads the one-time token from the URL fragment (`#token=...`), removes it from the address bar, and submits the new password. The token is never placed in a query string.
- `/security` (sidebar "Account security") lets a signed-in user change their password (the returned fresh token replaces the stored one) or sign out of all devices.
- The login page links to `/forgot-password`.
