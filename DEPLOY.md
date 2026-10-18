# Deploying this prototype (Lanford Health)

One Docker image: builds the React app, generates the synthetic data, serves everything from FastAPI
(`Dockerfile`). Nothing in the image needs a key; the GW Azure OpenAI key is an environment variable at the host.

## Render free tier (one click, about 10 minutes to first boot)

1. Open <https://render.com/deploy?repo=https://github.com/fsamedli/friction-finder-health> and sign in with GitHub.
   Render reads `render.yaml` (a Blueprint) and proposes one free web service named `friction-finder-health`.
2. It asks for `OPENAI_API_KEY`: paste the GW-provided key from the laptop's `prototype/.env`. Leave the
   other variables as proposed (the GW Azure endpoint and the gpt-5-mini deployment). Click Apply.
3. The first build takes about 5 to 10 minutes (npm build, pip install, data generation). The URL is
   `https://friction-finder-health.onrender.com` (Render may add a suffix if the name is taken; it shows the final URL).
4. Open the URL, user menu > **Reset demo**, check the demo clock reads Sept 15, and walk
   `docs/demo/DEMO_SCRIPT.md`.

Free-tier behaviour to plan around (per Render's free-plan docs; confirm on the dashboard):
- The service spins down after about 15 minutes with no traffic and takes up to a minute to wake. **Open the URL
  two minutes before showing it.**
- The disk is ephemeral: plans approved in the app, feedback and uploads vanish on every redeploy or restart.
  That is fine for a demo (Reset demo does the same thing on purpose).
- 512 MB RAM and a slow CPU: live model answers run at the same speed as on the laptop (the model does the
  waiting), but the first page after a wake is slower.
- Every push to the repo's default branch redeploys automatically.

Without the key the app still works in rules mode ("rules mode, no model"); the three scripted demo questions are
served from prepared answers either way.

## Run the same image locally

```bash
docker build -t friction-finder-health .
docker run --rm -p 8000:8000 --env-file .env friction-finder-health   # http://127.0.0.1:8000
```

## Other free hosts

The same Dockerfile runs on Hugging Face Spaces (Docker SDK, set `app_port: 8000` in the Space README, add the key
as a Space secret) or Fly.io / Google Cloud Run (both want a credit card on file). Netlify and Vercel are not a fit:
the API is a Python process with pandas, DuckDB and statsmodels, not static files or small serverless functions.
