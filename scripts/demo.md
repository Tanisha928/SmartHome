# Smart Home dashboard demo

1. Start the frontend with `cd frontend && VITE_DEMO_MODE=true npm run dev`.
2. Open `http://localhost:5173/login` and sign in with any email and password.
3. Show Live alerts, filter by severity, open an alert, and acknowledge it with a note.
4. Open History and export CSV; formula-like cells are neutralized.
5. Sign out, create an owner account, and show the friendly owner home/history views. Owner views omit confidence, model, and internal IDs.

For the real-stack demo, unset `VITE_DEMO_MODE`, start Docker Compose, seed the database, and use the edge simulator to produce a glass-break event.
