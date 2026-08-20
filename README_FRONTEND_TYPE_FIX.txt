Weam frontend TypeScript fix

Fixes React 19 / TypeScript error:
Cannot find namespace 'JSX'

Change:
JSX.Element[] -> ReactNode[]

No dependency changes.
No migration.

Run:
cd frontend
npm.cmd run typecheck
npm.cmd run build
