# NCRB NodeSpace
### Criminal Intelligence Core & Link Analysis System

NCRB NodeSpace is an end-to-end digital crime-intelligence and graph analytics platform. It automatically processes unstructured police First Information Reports (FIRs), Call Detail Records (CDRs), and judicial chargesheet PDFs into an interactive 3D force-directed WebGL knowledge graph.

## ✨ Features

- **Zero-Shot NLP Extraction** via GLiNER transformers and Indian forensic regex.
- **Graph Machine Learning** using PageRank, Betweenness Centrality, and Louvain Modularity clustering.
- **Pre-trained Random Forest ML Forensics Models** for Syndicate Risk, Entity Role classification, Bail eligibility, and Conviction propensity.
- **Section 63 BSA 2023 Digital Chain-of-Custody** with deterministic SHA-256 fingerprinting.
- **Interactive Multi-Tab Dashboard** featuring:
  - 3D WebGL NodeSpace
  - Chronological Crime Timeline
  - Syndicate Modularity Cells
  - BSA Evidence Audit Vault

---

## 📋 System Prerequisites

Ensure the following tools are installed before starting:

- **Python 3.10–3.12** (recommended)
  - [Download Python](https://www.python.org/downloads/)
  - **Windows:** Check **"Add python.exe to PATH"** during installation.
- **Git**
  - [Download Git](https://git-scm.com/)
- **Google Chrome, Microsoft Edge, or Firefox**
  - WebGL should be enabled.

---

## 🗂️ Project Structure

```text
ncrb-nodespace/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── ml/
│   │   │   └── crime_ml_bundle.joblib
│   │   └── services/
│   │       ├── evidence_vault.py
│   │       ├── graph_engine.py
│   │       ├── ml_service.py
│   │       ├── nlp_extractor.py
│   │       └── pdf_ingestion.py
│   │
│   ├── synthetic_crime_15k_cleaned.csv.xls
│   ├── train_ml.py
│   ├── requirements.txt
│   └── run.py
│
├── frontend/
│   └── index.html
│
└── README.md
```

> **Note:** `crime_ml_bundle.joblib` is generated during ML training.

---

## 🚀 Setup Guide

Follow these steps in order.

### 1. Clone the Repository

```bash
git clone https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git
cd <YOUR-REPO-NAME>
```

### 2. Navigate to the Backend

```bash
cd backend
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv
```

### 4. Activate the Virtual Environment

#### Windows — PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

> If you get a script execution policy error, run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

#### Windows — Command Prompt

```cmd
.venv\Scripts\activate.bat
```

#### macOS / Linux

```bash
source .venv/bin/activate
```

### 5. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Train the ML Forensics Models

```bash
python train_ml.py
```

### 7. Start the FastAPI Backend

```bash
python run.py
```

The server will start at:

```text
http://localhost:8000
```

#### Verify the Backend

**API Documentation**

```text
http://localhost:8000/docs
```

**Health Endpoint**

```text
http://localhost:8000/api/v1/health
```

---

## 🌐 Launch the Frontend

### Option A — Directly through the Backend

Navigate to:

```text
http://localhost:8000
```

### Option B — VS Code Live Server

Right-click:

```text
frontend/index.html
```

and select **Open with Live Server**.

---

## 🔍 How to Use the Application

### 1. Ingest FIR or Case Documents

1. Click the **+ INGEST FIR RECORD** button in the top-right corner.
2. Select a police FIR, CDR intercept report, or High Court judgment PDF.
3. Click **EXTRACT & ANALYZE**.

### 2. Explore the 3D NodeSpace

| Action | Control |
|---|---|
| Rotate | Left Mouse Button + Drag |
| Pan | Right Mouse Button + Drag |
| Zoom | Mouse Scroll Wheel |
| Inspect Entity | Click a Node |

### 3. Navigate the Operational Tabs

- **3D NodeSpace** — Visual WebGL network with threat halos and particle flow.
- **Timeline** — Chronological order of intercepts and seizures.
- **Syndicate Cells** — Louvain community partitions.
- **BSA Sec 63 Vault** — SHA-256 cryptographic fingerprints.

---

## 🎨 Entity Visual Legend

| Visual | Category | Description |
|---|---|---|
| 🔴 Crimson Red | High Threat Kingpins / Criminals | Threat score ≥ 70% (BNS 103, MCOCA) |
| 🟣 Purple | Suspects / Co-Accused | Intermediaries and co-conspirators |
| 🌹 Rose Pink | Registered FIR Cases | Formal crime cases |
| 🌊 Teal Cyan | Police Stations | Investigating jurisdictions |
| 🔵 Blue / Cyan | Phone Numbers | Intercepted mobile numbers |
| 🟢 Emerald Green | Bank Accounts | Financial mule accounts |
| 🔷 Indigo | Vehicles / Logistics | Transport and getaway vehicles |
| 🟡 Amber | Weapons / Contraband | Seized firearms and rifles |

---

## 🛠️ Troubleshooting

### `ModuleNotFoundError`

Ensure the virtual environment is active — you should see `(.venv)` in the terminal — and run:

```bash
pip install -r requirements.txt
```

### `Model crime_ml_bundle.joblib not found`

Run the ML training script from the `backend/` directory:

```bash
python train_ml.py
```

### CORS or Network Fetch Errors

Ensure the backend is running at:

```text
http://localhost:8000
```

### Graph Not Displaying

Open the application through:

```text
http://localhost:8000
```

or use VS Code Live Server.

Direct file paths can restrict WebGL functionality.

---

## 📌 Notes

- The ML model bundle is generated by `train_ml.py`.
- The synthetic dataset is used for ML model training.
- The frontend provides the 3D WebGL dashboard.
- The backend exposes the FastAPI application and processing services.
