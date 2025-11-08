  # 🧮 AutoSplit – Smart Bill Splitting & OCR Receipt Parser

  AutoSplit is a full-stack web application that automatically **extracts items, amounts, and participants from uploaded receipts** to split group expenses fairly.  
  It uses **OCR (Optical Character Recognition)** via **Tesseract**, **Natural Language Processing (NLP)** via **spaCy**, and a **Flask + React (Vite)** stack for a clean, real-time collaborative interface.

  ---

  ## 🚀 Features

  - 🧾 **Upload Receipts:** Extract item names and prices automatically from images.
  - 🤖 **Smart Parsing:** NLP-powered item-person detection using spaCy.
  - 👥 **Group Management:** Create groups, add members, and assign expenses dynamically.
  - ⚡ **Real-Time Updates:** Powered by Flask-SocketIO for instant synchronization.
  - 💳 **Stripe Integration:** (Optional) for managing or simulating payment flows.
  - 🐳 **Full Docker Support:** One command to start everything.

  ---

  ## 🧱 Tech Stack

  | Layer | Technology |
  |-------|-------------|
  | Frontend | React (Vite), JavaScript, Axios |
  | Backend | Flask (Python 3.11), Flask-SocketIO, Flask-CORS, SQLAlchemy |
  | OCR | pytesseract (Tesseract OCR Engine) |
  | NLP | spaCy |
  | Containerization | Docker & Docker Compose |

  ---

  ## ⚙️ Prerequisites

  Make sure you have these installed on your system:

  - [Docker](https://www.docker.com/get-started) ≥ 24.0  
  - [Docker Compose](https://docs.docker.com/compose/install/)  
  - (Optional for local dev)  
    - Python ≥ 3.11  
    - Node.js ≥ 18  

  ---

  ## 🐳 Running with Docker (recommended)

  1. **Clone the repository**
     ```bash
     git clone https://github.com/AdityaDotEnv/AutoSplit.git
     cd autosplit
     ```

  2. **Build and start the containers**
     ```bash
     docker compose up --build
     ```

  3. **Access the app**
     - Frontend → [http://localhost:5173](http://localhost:5173)
     - Backend API → [http://localhost:5000](http://localhost:5000)

  4. **Stop the containers**
     ```bash
     docker compose down
     ```

  ---

  ## 🧩 Project Structure

autosplit/
│
├── backend/
│ ├── app.py # Flask entry point
│ ├── models.py # SQLAlchemy models
│ ├── ocr_parser.py # OCR extraction using pytesseract
│ ├── nlp_parser.py # NLP logic using spaCy
│ ├── requirements.txt # Python dependencies
│ ├── Dockerfile # Backend container config
│ └── ...
│
├── frontend/
│ ├── src/ # React components
│ ├── package.json
│ ├── vite.config.js
│ ├── Dockerfile # Frontend container config
│ └── ...
│
├── docker-compose.yml # Combined stack configuration
└── README.md

---

## 🧠 Environment Variables

If you’re running locally or deploying, you can create `.env` files in each service folder.

### Backend (`backend/.env`)
FLASK_ENV=production
FLASK_APP=app.py
SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///db.sqlite3
TESSERACT_CMD=/usr/bin/tesseract

### Frontend (`frontend/.env`)
VITE_API_BASE_URL=http://localhost:5000

---

## 🧮 Local (non-Docker) Setup (optional)

If you prefer running locally without Docker:

### 1️⃣ Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python app.py

Backend runs on: http://localhost:5000

2️⃣ Frontend
cd frontend
npm install
npm run dev


Frontend runs on: http://localhost:5173
```
## 🔍 Common Issues

| Issue | Cause | Fix |
|-------|--------|-----|
| ❌ **tesseract is not installed or it's not in your PATH** | Tesseract not found inside container | Ensure Dockerfile includes `tesseract-ocr` and `TESSERACT_CMD=/usr/bin/tesseract` |
| ❌ **numpy.dtype size changed** | NumPy 2.x / spaCy mismatch | Use `numpy==1.24.4` and `thinc==8.1.12` |
| ⚠️ **Frontend not accessible** | Wrong port mapping | Ensure `5173:5173` in `docker-compose.yml` |
| ⚠️ **Backend API CORS issues** | Missing CORS config | Add `from flask_cors import CORS; CORS(app)` in Flask |
