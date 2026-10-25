// Debug preload: record provider traffic (never headers or credentials).
// FETCHLOG_MODE=errors keeps only non-OK, non-429 responses: the request body and the error body.
import { writeFileSync, mkdirSync } from 'node:fs';
const dir = process.env.FETCHLOG_DIR;
const errorsOnly = process.env.FETCHLOG_MODE === 'errors';
if (dir) {
  const orig = globalThis.fetch;
  let n = 0;
  let made = false;
  const ensure = () => { if (!made) { mkdirSync(dir, { recursive: true }); made = true; } };
  globalThis.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url ?? String(input);
    const tag = `${process.pid}-${String(++n).padStart(4, '0')}`;
    if (!errorsOnly) {
      ensure();
      if (typeof init.body === 'string') writeFileSync(`${dir}/${tag}.req.json`, init.body);
      writeFileSync(`${dir}/${tag}.url.txt`, url.replace(/api-key=[^&]*/g, 'api-key=REDACTED'));
    }
    const res = await orig(input, init);
    if (!errorsOnly) writeFileSync(`${dir}/${tag}.status.txt`, String(res.status));
    if (!res.ok && !(errorsOnly && res.status === 429)) {
      ensure();
      if (errorsOnly) {
        if (typeof init.body === 'string') writeFileSync(`${dir}/${tag}.req.json`, init.body);
        writeFileSync(`${dir}/${tag}.status.txt`, String(res.status));
      }
      try { writeFileSync(`${dir}/${tag}.err.txt`, await res.clone().text()); } catch (e) { writeFileSync(`${dir}/${tag}.err.txt`, 'clone failed: ' + e); }
    }
    return res;
  };
}
