# Tamil Nadu Politics Brief
*"Understand Tamil Nadu Politics. One Briefing at a Time."*

A fully automated, non-partisan, zero-cost (`₹0/month`) digital political newspaper and searchable research archive covering Tamil Nadu politics. Published twice daily at **6:00 AM IST** and **6:00 PM IST**.

---

## 1. System Overview & Architecture
- **Frontend:** Static HTML5, Editorial CSS, and Vanilla JavaScript hosted for free on **GitHub Pages**.
- **Automation:** Twice-daily **GitHub Actions** cron workflows (`morning-edition.yml` and `evening-edition.yml`).
- **Storage:** Permanent Markdown (`.md`) and JSON (`.json`) files inside `archive/YYYY/MM/` plus a lightweight client-side search index (`data/archive-index.json`).
- **AI Summarization:** Uses Google's **Gemini API Free Tier** (`gemini-2.5-flash`) with programmatic URL validation and a deterministic extractive fallback so the pipeline never fails or incurs billing charges.

---

## 2. Setup & Local Development

### Prerequisites
- Python 3.10 or newer
- Git

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/VISHNU-ARAVIND-99/tamil-nadu-politics-brief.git
   cd tamil-nadu-politics-brief
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. (Optional) Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Add your free `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/).

### Running Tests
Execute the verification test suite:
```bash
python -m unittest discover -s tests -v
```

### Running the Pipeline Locally
To generate the morning edition:
```bash
python -m scripts.publish_edition --edition morning
```
To generate the evening edition:
```bash
python -m scripts.publish_edition --edition evening
```

---

## 3. GitHub Deployment Setup

### Enable GitHub Pages
1. Go to repository **Settings** &rarr; **Pages**.
2. Under **Build and deployment** &gt; **Source**, select **Deploy from a branch**.
3. Branch: `main`, folder: `/ (root)`.
4. Click **Save**.

### GitHub Actions Secrets & Permissions
1. Under **Settings** &rarr; **Secrets and variables** &rarr; **Actions**:
   - Add Secret: `GEMINI_API_KEY` (Free tier key from Google AI Studio).
2. Under **Settings** &rarr; **Actions** &rarr; **General** &rarr; **Workflow permissions**:
   - Select **Read and write permissions** (required for automated commits to push editions to the repository).

---

## 4. Editorial Integrity & Neutrality
- **Balanced Coverage:** Tracks DMK, AIADMK, BJP, INC, TVK, PMK, NTK, VCK, MDMK, DMDK, AMMK, and Left parties proportionally.
- **Copyright Compliance:** Adheres strictly to `robots.txt`, never stores full articles, and always cites primary sources with direct links.
- **Zero Hallucinated Links:** Every URL produced is programmatically verified against the collected RSS registry.
- **Deterministic Fallback:** If Gemini API key is missing or rate limits occur, the pipeline falls back to an extractive summarizer to guarantee reliable publishing.
