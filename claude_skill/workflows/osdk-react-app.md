# Workflow: build an OSDK React app

A minimal React app that reads ontology objects and applies an action, with
Vite, `@osdk/client`, `@osdk/oauth` and `@osdk/react`. Write it by hand from
this recipe: `npx @osdk/create-app` needs a terminal (it fails with
`ERR_TTY_INIT_FAILED`, or hangs under a pseudo-terminal, even with every
option given), so an agent can't use it.

The names below are an example: an object type `Order` with properties
`orderId`, `status` and `assignee`, and an action `assign-order` with the
parameters `order` and `assignee`. Replace them with yours, and every
`<placeholder>` with a real value.

## What you need from the user

- **The ontology and the types**: `pltr ontology list` gives the ontology;
  `pltr context ontology <ontology> --types Order` gives an object type's
  properties, links, and the actions and queries that use it.
- **An OAuth client ID** for signing users in: a public client of a
  Developer Console application that can use the object and action types.
  pltr can't create one. Generating the package doesn't need it.
- **The redirect URIs registered for that client** in Developer Console:
  `http://localhost:8080/auth/callback` for development, and
  `https://<app-host>/auth/callback` where the app will be hosted.

## 1. Generate the package

From the app's directory (the dependency path is relative to it):

```bash
mkdir orders-app && cd orders-app
pltr osdk generate --ontology <ontology> --object-type Order \
  --action-type assign-order --out ./osdk --package-name @orders-app/sdk --format json
```

The result has the `dependency` line, the `peerDependencies` and
`reactDependencies` to add, the `overrides` entry and the `ontologyRid`.
Use the versions it prints: they follow the generator pltr pins. To add
types later, run it again with every type and `--replace`.

## 2. package.json

```json
{
  "name": "orders-app",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@orders-app/sdk": "file:./osdk/@orders-app/sdk",
    "@osdk/client": "2.87.0",
    "@osdk/oauth": "1.14.0",
    "@osdk/react": "2.87.0",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "6.30.6"
  },
  "devDependencies": {
    "@types/react": "18.3.31",
    "@types/react-dom": "18.3.7",
    "@vitejs/plugin-react": "4.7.0",
    "typescript": "5.9.3",
    "vite": "6.4.5"
  },
  "overrides": {
    "@osdk/api": "2.87.0"
  }
}
```

Keep the `overrides` entry: `@osdk/react` 2.87.0 accepts any `@osdk/api`
2.x from 2.87.0, so npm installs a newer one for it (2.88.0) while
`@osdk/client` 2.87.0 uses 2.87.0, and `tsc` fails with TS2322 on the
generated types. (pnpm: `"pnpm": {"overrides": ...}`; yarn:
`"resolutions"`.)

## 3. vite.config.ts

In development the app talks to `http://localhost:8080`, and Vite proxies
Foundry's API and OAuth paths to the stack, so the stack needs no CORS
setup for localhost:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      // Must match the registered redirect URI; fail rather than move port.
      port: 8080,
      strictPort: true,
      proxy: {
        "^(/multipass/api|/api)": {
          target: env.FOUNDRY_STACK_URL,
          changeOrigin: true,
          secure: true,
        },
      },
    },
  };
});
```

## 4. tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
```

## 5. .env.development and .env.production

None of these is a secret (a public client has no secret). The ontology RID
is `ontologyRid` in the output of `pltr osdk generate`.

```bash
# .env.development
FOUNDRY_STACK_URL=https://<stack>
VITE_FOUNDRY_API_URL=http://localhost:8080
VITE_FOUNDRY_REDIRECT_URL=http://localhost:8080/auth/callback
VITE_FOUNDRY_CLIENT_ID=<client-id>
VITE_FOUNDRY_ONTOLOGY_RID=<ontology-rid>
```

```bash
# .env.production
VITE_FOUNDRY_API_URL=https://<stack>
VITE_FOUNDRY_REDIRECT_URL=https://<app-host>/auth/callback
VITE_FOUNDRY_CLIENT_ID=<client-id>
VITE_FOUNDRY_ONTOLOGY_RID=<ontology-rid>
```

## 6. index.html

Vite fills the meta tags from the `.env` file of the mode it runs in:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="osdk-clientId" content="%VITE_FOUNDRY_CLIENT_ID%" />
    <meta name="osdk-redirectUrl" content="%VITE_FOUNDRY_REDIRECT_URL%" />
    <meta name="osdk-foundryUrl" content="%VITE_FOUNDRY_API_URL%" />
    <meta name="osdk-ontologyRid" content="%VITE_FOUNDRY_ONTOLOGY_RID%" />
    <title>Orders</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

## 7. src/client.ts

```ts
import { createClient, type Client } from "@osdk/client";
import { createPublicOauthClient } from "@osdk/oauth";

function meta(name: string): string {
  const value = document.querySelector(`meta[name="${name}"]`)?.getAttribute("content");
  if (!value || value.includes("%")) throw new Error(`Missing meta tag ${name}`);
  return value;
}

const foundryUrl = meta("osdk-foundryUrl");

export const auth = createPublicOauthClient(
  meta("osdk-clientId"),
  foundryUrl,
  meta("osdk-redirectUrl"),
);

export const client: Client = createClient(foundryUrl, meta("osdk-ontologyRid"), auth);
export default client;
```

## 8. src/main.tsx

```tsx
import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { OsdkProvider } from "@osdk/react";
import AuthCallback from "./AuthCallback";
import Home from "./Home";
import client from "./client";

const router = createBrowserRouter(
  [
    { path: "/", element: <Home /> },
    { path: "/auth/callback", element: <AuthCallback /> },
  ],
  { basename: import.meta.env.BASE_URL },
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <OsdkProvider client={client}>
      <RouterProvider router={router} />
    </OsdkProvider>
  </StrictMode>,
);
```

## 9. src/AuthCallback.tsx

Foundry sends the user back to `/auth/callback` after sign-in; calling
`signIn()` again there stores the token:

```tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { auth } from "./client";

function AuthCallback(): React.ReactElement {
  const [error, setError] = useState<string | undefined>(undefined);
  const navigate = useNavigate();

  // StrictMode runs this effect twice in development; the second call is harmless.
  useEffect(() => {
    const signIn = (auth as { signIn?: () => Promise<unknown> }).signIn;
    if (typeof signIn !== "function") {
      navigate("/", { replace: true });
      return;
    }
    signIn()
      .then(() => navigate("/", { replace: true }))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [navigate]);
  return <div>{error != null ? error : "Authenticating…"}</div>;
}

export default AuthCallback;
```

## 10. src/Home.tsx

The package exports each object type under its API name and each action in
camelCase (`assign-order` becomes `assignOrder`); see
`osdk/@orders-app/sdk/ontology/` for the exact names. Action parameters are
the action's parameter API names.

```tsx
import { useState } from "react";
import type { Osdk } from "@osdk/client";
import { useOsdkAction, useOsdkObjects } from "@osdk/react";
import { assignOrder, Order } from "@orders-app/sdk";

function Assign({ order }: { order: Osdk.Instance<Order, "$allBaseProperties"> }) {
  const [assignee, setAssignee] = useState("");
  const [error, setError] = useState<string | null>(null);
  const assign = useOsdkAction(assignOrder);

  async function submit() {
    setError(null);
    try {
      await assign.applyAction({ order, assignee: assignee.trim() });
      setAssignee("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <span>
      <input value={assignee} placeholder="Assignee" onChange={(e) => setAssignee(e.target.value)} />
      <button disabled={assignee.trim() === "" || assign.isPending} onClick={submit}>
        Assign
      </button>
      {error && <span role="alert">{error}</span>}
    </span>
  );
}

export default function Home() {
  const { data: orders, isLoading, error } = useOsdkObjects(Order, { pageSize: 100 });
  return (
    <main>
      <h1>Orders</h1>
      {isLoading && <p>Loading…</p>}
      {error && <p role="alert">{String(error)}</p>}
      <table>
        <tbody>
          {(orders ?? []).map((o) => (
            <tr key={o.$primaryKey}>
              <td>{o.orderId}</td>
              <td>{o.status}</td>
              <td>{o.assignee ?? ""}</td>
              <td>
                <Assign order={o} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

## 11. Install, check, run

```bash
npm install
npm run typecheck      # the TS2322 check: see the overrides entry above
npm run dev            # http://localhost:8080; sign in with Foundry
npm run build          # dist/, for hosting
```

To host it on Foundry, deploy `dist/` to the application's website (the
user does the one-time hosting setup first; see SKILL.md §6e):

```bash
pltr site deploy dist --application <application-rid> --auto-version package-json --yes --format json
```

Before you call an action for real, check it with
`pltr ontology action-validate <ontology> assign-order '{"order": "<primary-key>", "assignee": "Jane"}'`.

## Operational notes

- **Redirect URIs**: the client needs both
  `http://localhost:8080/auth/callback` and
  `https://<app-host>/auth/callback` registered in Developer Console; a
  sign-in from anywhere else fails.
- **Port**: the dev server port must match the redirect URI. `strictPort`
  makes Vite fail when 8080 is taken instead of quietly using another port.
- **Hosting**: a hosted site calls the stack from its own domain (no proxy),
  so that domain needs a network-ingress allowlist entry on the stack
  (Control Panel) before the app can reach the API. Deploy with `pltr site deploy`; bump
  `version` in package.json for each deploy, since a version can't be uploaded
  twice.
- **Regenerating**: after the types or the ontology change, run
  `pltr osdk generate ... --replace` with every type the app uses, then
  `npm install` and `npm run typecheck`.
- **Builds elsewhere** (CI, a hosting build) need `osdk/` too, since the
  app depends on it with `file:`: commit it, or generate it before
  `npm install` there.
