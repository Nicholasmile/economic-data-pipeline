# Deploy on Streamlit Community Cloud

Streamlit Community Cloud is the proposed free hosting option for this MVP. It
runs Streamlit directly from a GitHub repository. An account is needed to manage
deployment; visitors to a public app do not need application authentication.

**Do not publish until the project owner approves the repository contents and
public deployment.** No public deployment has been performed.

## Prepare locally

1. Run `python -m unittest discover -s tests -v` using the project's `.venv` Python.
2. Run `python scripts/smoke_world_bank.py` to confirm connectivity and review
   source dates. This live check creates only platform caches.
3. Start `python -m streamlit run app.py` and verify tables, missing values,
   comparison charts, definitions and both download formats.
4. Review files for publication. `.gitignore` excludes both virtual environments,
   platform caches and Streamlit secrets. Original public-source datasets are
   retained, but review them before uploading. No credential is required in the app.
   You may omit original data from hosting; the archive viewer handles absent files.

The current folder is not a Git repository. After approval, create a repository and
upload the reviewed project. Do not commit `.venv`, `.venv-1`, caches or secrets.
For private repository hosting, check current Community Cloud account options.

## Hosting settings

1. Sign into [Streamlit Community Cloud](https://share.streamlit.io/) and connect
   the approved GitHub repository.
2. Choose **Create app**, the repository and branch, and main file **`app.py`**.
3. In Advanced settings choose **Python 3.14** if offered. That is the locally
   verified version. If unavailable, choose a supported Python version of at least
   3.11 and test these pinned requirements in that environment before publishing.
   Hosting Python availability changes; do not list Python as a pip requirement.
4. Hosting installs `requirements.txt`; the theme comes from
   `.streamlit/config.toml`. No secrets, database, OS packages or API key are needed.
5. Deploy only after final approval, then verify the public URL in another session.

Official guides:
[Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy),
[dependencies](https://docs.streamlit.io/deploy/concepts/dependencies), and
[hosting limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status).

## After deployment

- Build a small Nigeria/Ghana request and download CSV/Excel.
- Confirm original indicator codes and country identity in output.
- Inspect missing-value and retrieval-status reports, as well as source dates.
- Restarts may remove disk caches. Save downloaded workbooks for reproducibility.
- Free hosting has resource limits and may sleep when idle. Review current limits
  before relying on it for a classroom or large research group.
- Updating the repository can redeploy the app. Review changes and rerun tests
  before pushing releases.

## Troubleshooting

- **Catalogue failure:** check network/API availability and retry. Valid caches
  remain usable offline; expired ones are visibly labelled.
- **Blank observations:** check definitions and coverage; do not assume zeros.
- **Retrieval failed:** separate from confirmed missing observations; refresh
  when connectivity returns.
- **Install error:** compare hosting Python and requirements with the locally
  verified environment; retain logs for diagnosis.
- **Windows activation policy:** invoke `.\.venv\Scripts\python.exe` directly.
