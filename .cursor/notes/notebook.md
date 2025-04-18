# Notebook 

## 2025-04-18: Frontend Debugging Session Notes

*   **Issue:** UI not updating after code changes (Archive feature in `ManageScriptsPage`).
*   **Initial Hypothesis:** Docker volume mount or build cache issues.
*   **Finding 1:** Discovered parameter type bug in `GenerationForm.tsx`. `api.listScripts` was called with `{sort_by: ...}` instead of `boolean`. Fixed this call.
*   **Finding 2:** Parameter bug fix *did not* resolve UI update issue.
*   **Finding 3:** Switching to local `npm run dev` revealed port 5173 was blocked by a zombie process. New server started on 5174.
*   **Finding 4:** Even after fixing the port and clearing local caches (`node_modules`, `.vite`), the local dev server *still* failed to serve the updated `ManageScriptsPage.tsx` code (verified by changing `<h2>` title).
*   **Finding 5:** The local dev server *did* reflect changes made to `main.tsx` (via `console.log`), indicating HMR/watching worked for *some* files but not others.
*   **Finding 6:** Build errors related to missing `@mantine/dates` package and incorrect imports (`BatchListPage` vs `BatchesPage`, relative paths in `ManageScriptsPage`, etc.) were identified and fixed during static build attempts.
*   **Finding 7:** Static build + Nginx initially failed due to Nginx error `host not found in upstream "backend"`. Resolved by adding `resolver 127.0.0.11` and using a variable for `proxy_pass` in `nginx.conf`.
*   **Conclusion:** Root cause seems to be severe instability/caching issues with the Vite dev server (both locally and in Docker on this machine) specifically related to updating certain components. The Static Build + Nginx approach is the working stable configuration. 