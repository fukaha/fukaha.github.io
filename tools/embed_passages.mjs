// Meaning vectors of the search passages (tools/build_search.py), for the meaning search on /ara/.
//
// Reads a passages.jsonl file (one cleaned passage text a line, in index order) and embeds each
// passage with Xenova/multilingual-e5-small, the model the browser loads for the query. The full
// vectors are kept in <work>/vec.f32 (so the run can be stopped and started again), then packed
// for the site by --pack: the mean of all vectors is taken away from each and every dimension is
// cut to a few bits (see pack()). Without taking the mean away the signs of the dimensions say
// almost nothing, since all passages of the corpus point much the same way.
//
// Usage: node tools/embed_passages.mjs <passages.jsonl> [work folder]
//        node tools/embed_passages.mjs --pack [work folder]
// It needs @huggingface/transformers (npm install @huggingface/transformers@3) and takes some
// hours on a few processor cores.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIM = 384;
const args = process.argv.slice(2);

if (args[0] === '--pack') pack(args[1] || '.');
else await embed(args[0], args[1] || '.');

async function embed(src, work) {
  const { pipeline, env } = await import('@huggingface/transformers');
  env.cacheDir = path.join(work, 'models');
  const texts = fs.readFileSync(src, 'utf8').trim().split('\n').map(JSON.parse);
  const file = path.join(work, 'vec.f32');
  const done0 = fs.existsSync(file) ? Math.floor(fs.statSync(file).size / (DIM * 4)) : 0;
  if (fs.existsSync(file)) fs.truncateSync(file, done0 * DIM * 4);
  const fd = fs.openSync(file, 'a');
  const ext = await pipeline('feature-extraction', 'Xenova/multilingual-e5-small', { dtype: 'q8' });
  const BATCH = 16;
  const t0 = Date.now();
  for (let i = done0; i < texts.length; i += BATCH) {
    const batch = texts.slice(i, i + BATCH).map(t => 'passage: ' + t);
    const o = await ext(batch, { pooling: 'mean', normalize: true, truncation: true, max_length: 512 });
    fs.writeSync(fd, Buffer.from(o.data.buffer, o.data.byteOffset, batch.length * DIM * 4));
    const done = i + batch.length;
    if (done % (BATCH * 50) === 0 || done === texts.length)
      console.log(`${done}/${texts.length} (${((Date.now() - t0) / 60000).toFixed(1)} dk)`);
  }
  fs.closeSync(fd);
  pack(work);
}

// data/ara/vec.bin: a header of the DIM float32 means, then for each passage DIM 4-bit codes, two
// to a byte (low half first). A code c stands for the centred value (c - 7.5) * step, with the
// float32 step after the means in the header; the browser scores a passage by the dot product of
// the centred query with these values.
function pack(work) {
  const buf = fs.readFileSync(path.join(work, 'vec.f32'));
  const n = Math.floor(buf.length / (DIM * 4));
  const V = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + n * DIM * 4));
  const mu = new Float32Array(DIM);
  for (let i = 0; i < n; i++) for (let k = 0; k < DIM; k++) mu[k] += V[i * DIM + k] / n;
  let sq = 0;
  for (let i = 0; i < V.length; i++) { const x = V[i] - mu[i % DIM]; sq += x * x; }
  const step = 2.6 * Math.sqrt(sq / V.length) / 7.5; // ±2.6 standard deviations over 16 levels
  const out = Buffer.alloc(DIM * 4 + 4 + n * DIM / 2);
  Buffer.from(mu.buffer).copy(out, 0);
  out.writeFloatLE(step, DIM * 4);
  const base = DIM * 4 + 4;
  for (let i = 0; i < n; i++) for (let k = 0; k < DIM; k++) {
    const c = Math.max(0, Math.min(15, Math.round((V[i * DIM + k] - mu[k]) / step + 7.5)));
    out[base + i * DIM / 2 + (k >> 1)] |= k & 1 ? c << 4 : c;
  }
  fs.writeFileSync(path.join(ROOT, 'data/ara/vec.bin'), out);
  console.log('data/ara/vec.bin yazıldı:', n, 'pasaj,', out.length, 'bayt');
}
