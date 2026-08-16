# PaperDaily Local Edition

The local edition is for researchers who want PaperDaily without GitHub Actions or GitHub Pages. It uses the same retrieval, filtering, AI ranking, summaries, archive, and HTML interface as the hosted version.

## What you need

- Windows, macOS, or Linux.
- Python 3.11 or newer.
- Internet access for PubMed, bioRxiv, medRxiv, arXiv, and your AI provider.
- One API token, such as a DeepSeek API key.

## The two files you normally edit

### 1. `config.yaml`

Use this file to configure:

- your research field and discovery terms;
- deterministic prefilter rules;
- `prefilter.max_candidates`;
- `ai.max_analyzed`;
- `site.featured_count`;
- AI provider/model;
- timezone;
- optional local server settings.

The included `config.yaml` is the sleep-neuroscience example. `config.template.yaml` is a generic starting point for another field.

### 2. `api_token.txt`

Copy:

```text
api_token.example.txt
```

to:

```text
api_token.txt
```

Then replace the placeholder with your API token on the first line.

`api_token.txt` is ignored by Git and should never be shared.

## Windows: easiest start

Double-click:

```text
START_PAPERDAILY_WINDOWS.bat
```

On the first run it will:

1. create a private Python virtual environment;
2. install the required Python packages;
3. create `api_token.txt` if it does not exist;
4. ask you to paste the API token if needed.

Run the file again after saving the token. PaperDaily will refresh the literature, start a local web server, and open the HTML dashboard in your default browser.

## macOS / Linux

From Terminal inside the PaperDaily folder:

```bash
bash START_PAPERDAILY_MAC_LINUX.sh
```

The script creates the virtual environment, installs dependencies, and starts PaperDaily.

## What happens when PaperDaily starts

By default the local launcher:

1. reads `config.yaml`;
2. loads `api_token.txt` into the API environment variable configured by `ai.api_key_env`;
3. runs the literature pipeline;
4. writes the archive under `data/` and compact web data under `site/data/`;
5. serves `site/` on localhost;
6. opens the browser automatically.

The default local address is:

```text
http://127.0.0.1:8765/
```

Keep the terminal/command window open while browsing. Press `Ctrl+C` to stop the local server.

## Optional local settings

Add this to `config.yaml` if you want to change local behavior:

```yaml
local:
  port: 8765
  refresh_on_start: true
```

Set `refresh_on_start: false` if you only want to browse previously generated local data without fetching new papers each time.

## Downloadable ZIP

The hosted PaperDaily site automatically builds a synchronized local ZIP during GitHub Pages deployment:

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

The ZIP does not contain any API token, GitHub secret, historical backend data, or virtual environment.

## Build the ZIP yourself

From the repository root:

```bash
python tools/build_local_bundle.py
```

The default output is:

```text
dist/PaperDaily-local.zip
```

## Security

Do not put the API token into HTML or JavaScript. The local launcher keeps it on the Python side, so it is not exposed to the browser page.

Do not upload `api_token.txt` when sharing the local folder.
