/**
 * SUUKALIA AUTOMATION v2.0 - Railway Deployment
 * NanoBanana Pro 2 + Seedream 5.0 Lite + Kling O3 Pro
 */

const Airtable = require('airtable');
const axios    = require('axios');
const fetch    = require('node-fetch');

const AIRTABLE_API_KEY  = process.env.AIRTABLE_API_KEY;
const AIRTABLE_BASE_ID  = process.env.AIRTABLE_BASE_ID  || 'apprXRnZO29hupbwl';
const WAVESPEED_API_KEY = process.env.WAVESPEED_API_KEY;
const GROK_API_KEY      = process.env.GROK_API_KEY;
const GEMINI_API_KEY    = process.env.GEMINI_API_KEY;

const MODELS = {
  faceSwap  : 'google/nano-banana-2/edit',
  imageGen  : 'bytedance/seedream-v5.0-lite',
  video     : 'kwaivgi/kling-video-o3-pro/image-to-video',
  grokVision: 'grok-4.20-beta-latest-non-reasoning',
  gemini    : 'gemini-2.0-flash',
};

const WAVESPEED_BASE = 'https://api.wavespeed.ai/api/v3';
const base = new Airtable({ apiKey: AIRTABLE_API_KEY }).base(AIRTABLE_BASE_ID);

let consecutiveFailures = 0;
const MAX_FAILURES   = 5;
const PAUSE_DURATION = 60 * 1000;

const log = {
  info : (id, msg) => console.log('-> [' + id + '] ' + msg),
  ok   : (id, msg) => console.log('[OK] [' + id + '] ' + msg),
  err  : (id, msg) => console.log('[ERR] [' + id + '] ' + msg),
  warn : (msg)     => console.log('[WARN] ' + msg),
  title: (msg)     => console.log('\n=== ' + msg + ' ==='),
};

async function getConfig() {
  const records = await base('Configuration').select({ maxRecords: 1 }).firstPage();
  if (!records.length) throw new Error('No configuration found in Airtable');
  const c = records[0].fields;
  return {
    numImages     : c['num_images']      || 1,
    faceReference : c['Face_Reference']  ? c['Face_Reference'][0].url  : null,
    bodyReference : c['Body_Reference']  ? c['Body_Reference'][0].url  : null,
    promptProvider: c['Prompt_Provider'] || 'Gemini',
    imageModel    : c['Image_Model']     || 'Seedream 4.5',
    videoModel    : c['Video_Model']     || null,
    imageSize     : c['Image_Size']      || '1024x1536',
  };
}

async function analyzeWithGrok(imageUrl, recordId) {
  log.info(recordId, 'Analyzing with Grok (NSFW)...');
  const res = await axios.post(
    'https://api.x.ai/v1/chat/completions',
    {
      model: MODELS.grokVision,
      messages: [{
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: imageUrl } },
          { type: 'text', text: 'You are an expert NSFW AI image prompt engineer. Analyze this image and write a detailed, explicit generation prompt for Seedream/NanoBanana. Describe: exact pose and body position, outfit/clothing detail, setting/background, lighting, photography style. Style: shot on iPhone, candid, no filter, authentic. 60-100 words. Output ONLY the prompt.' }
        ]
      }],
      max_tokens: 300,
      temperature: 0.8,
    },
    { headers: { Authorization: 'Bearer ' + GROK_API_KEY } }
  );
  return res.data.choices[0].message.content.trim();
}

async function analyzeWithGemini(imageUrl, recordId) {
  log.info(recordId, 'Analyzing with Gemini (SFW)...');
  const b64 = await urlToBase64(imageUrl);
  const res = await axios.post(
    'https://generativelanguage.googleapis.com/v1beta/models/' + MODELS.gemini + ':generateContent?key=' + GEMINI_API_KEY,
    {
      contents: [{
        parts: [
          { text: 'You are an expert AI image prompt engineer. Analyze this image and write a detailed SFW generation prompt for Seedream/NanoBanana. Describe: exact pose and body language, outfit and style, setting/background, lighting, photography style. Style: shot on iPhone, candid, no filter, authentic. 60-100 words. Output ONLY the prompt.' },
          { inline_data: { mime_type: 'image/jpeg', data: b64 } }
        ]
      }],
      generationConfig: { maxOutputTokens: 300, temperature: 0.8 },
    }
  );
  return res.data.candidates[0].content.parts[0].text.trim();
}

async function generateWithNanoBanana(prompt, faceUrl, sourceUrl, recordId) {
  log.info(recordId, 'Generating with NanoBanana Pro 2...');
  const payload = { images: [sourceUrl], prompt, strength: 0.75, output_quality: 95 };
  if (faceUrl) payload.face_image = faceUrl;
  return await wavespeedJob(MODELS.faceSwap, payload, recordId);
}

async function generateWithSeedream(prompt, faceUrl, recordId) {
  log.info(recordId, 'Generating with Seedream 5.0 Lite...');
  const payload = { prompt, image_size: '1024x1536', num_inference_steps: 30, enable_safety_checker: false };
  if (faceUrl) { payload.reference_image = faceUrl; payload.reference_strength = 0.85; }
  return await wavespeedJob(MODELS.imageGen, payload, recordId);
}

async function generateVideo(imageUrl, prompt, recordId) {
  log.info(recordId, 'Generating video with Kling O3 Pro...');
  const payload = { image: imageUrl, prompt: prompt + ', smooth cinematic motion', duration: 5 };
  return await wavespeedJob(MODELS.video, payload, recordId);
}

async function wavespeedJob(modelId, payload, recordId) {
  const headers = { Authorization: 'Bearer ' + WAVESPEED_API_KEY, 'Content-Type': 'application/json' };
  const sub = await axios.post(WAVESPEED_BASE + '/' + modelId, payload, { headers });
  const predId = sub.data && sub.data.data ? sub.data.data.id : sub.data.id;
  if (!predId) throw new Error('Submit failed: ' + JSON.stringify(sub.data));
  log.info(recordId, 'Polling ' + predId + '...');
  for (let i = 0; i < 120; i++) {
    await sleep(3000);
    const poll = await axios.get(WAVESPEED_BASE + '/predictions/' + predId, { headers });
    const status = poll.data && poll.data.data ? poll.data.data.status : poll.data.status;
    const output = poll.data && poll.data.data ? poll.data.data.outputs : poll.data.outputs;
    if (status === 'completed' || status === 'succeeded') {
      return (Array.isArray(output) ? output : [output]).filter(Boolean);
    }
    if (status === 'failed' || status === 'error') {
      const errMsg = poll.data && poll.data.data ? poll.data.data.error : poll.data.error;
      throw new Error('Job failed: ' + errMsg);
    }
    if (i % 10 === 0 && i > 0) log.info(recordId, '  still processing... ' + (i * 3) + 's');
  }
  throw new Error('Wavespeed job timed out');
}

async function processRecord(record, cfg) {
  const id = record.id;
  const f  = record.fields;
  if (consecutiveFailures >= MAX_FAILURES) {
    log.warn('Circuit breaker: pausing 60s...');
    await sleep(PAUSE_DURATION);
    consecutiveFailures = 0;
  }
  try {
    const imgs = f['Prompt_Image'];
    if (!imgs || !imgs.length) { log.info(id, 'No prompt image, skipping'); return; }
    const sourceUrl = imgs[0].url;
    log.info(id, 'Prompt_Image detected');
    const isNSFW = cfg.promptProvider === 'Grok';
    const prompt = isNSFW
      ? await analyzeWithGrok(sourceUrl, id)
      : await analyzeWithGemini(sourceUrl, id);
    log.ok(id, 'Prompt: "' + prompt.substring(0, 70) + '..."');
    await base('Generation').update(id, { Prompt: prompt, 'Error Message': '' });
    const allUrls = [];
    for (let i = 0; i < cfg.numImages; i++) {
      log.info(id, 'Image ' + (i + 1) + '/' + cfg.numImages + '...');
      const urls = cfg.imageModel && cfg.imageModel.toLowerCase().includes('nano')
        ? await generateWithNanoBanana(prompt, cfg.faceReference, sourceUrl, id)
        : await generateWithSeedream(prompt, cfg.faceReference, id);
      allUrls.push(...urls);
    }
    await base('Generation').update(id, { 'Generated Images': allUrls.map(u => ({ url: u })) });
    log.ok(id, allUrls.length + ' image(s) saved to Airtable!');
    consecutiveFailures = 0;
    if (cfg.videoModel && allUrls[0]) {
      try {
        const vids = await generateVideo(allUrls[0], prompt, id);
        if (vids[0]) log.ok(id, 'Video: ' + vids[0]);
      } catch (e) { log.warn('Video skipped: ' + e.message); }
    }
  } catch (err) {
    consecutiveFailures++;
    const msg = err.response && err.response.data ? JSON.stringify(err.response.data) : err.message;
    log.err(id, 'Error: ' + msg);
    await base('Generation').update(id, { 'Error Message': msg }).catch(() => {});
  }
}

async function main() {
  log.title('SUUKALIA AUTOMATION v2.0');
  console.log('NanoBanana Pro 2 + Seedream 5.0 Lite + Kling O3 Pro\n');
  if (!AIRTABLE_API_KEY || !WAVESPEED_API_KEY) {
    console.error('[ERR] Missing API keys! Set environment variables in Railway.');
    process.exit(1);
  }
  log.title('Reading Airtable config');
  const cfg = await getConfig();
  console.log('  Prompt Provider: ' + cfg.promptProvider);
  console.log('  Image Model:     ' + cfg.imageModel);
  console.log('  Num Images:      ' + cfg.numImages);
  console.log('  Face Reference:  ' + (cfg.faceReference ? 'YES' : 'NO') + '\n');
  log.title('Fetching pending records');
  const records = await base('Generation')
    .select({ filterByFormula: "AND({Prompt_Image} != '', {Prompt} = '')" })
    .all();
  console.log('  Found ' + records.length + ' records to process\n');
  if (!records.length) { console.log('Nothing to do. Exiting.'); return; }
  for (const rec of records) {
    await processRecord(rec, cfg);
    await sleep(1000);
  }
  log.title('Done!');
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function urlToBase64(url) {
  const res = await fetch(url);
  const buf = await res.buffer();
  return buf.toString('base64');
}

main().catch(e => { console.error('Fatal:', e.message); process.exit(1); });
