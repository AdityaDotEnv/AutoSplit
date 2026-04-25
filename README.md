<div align="center">
  <h1>🧮 AutoSplit</h1>
  <p><strong>A Highly Deterministic, Real-Time Intelligent Bill Splitting & Receipt Parsing Engine</strong></p>

  <!-- Badges -->
  <p>
    <img src="https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB" alt="React" />
    <img src="https://img.shields.io/badge/vite-%23646CFF.svg?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
    <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python" />
    <img src="https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
    <img src="https://img.shields.io/badge/Socket.io-black?style=for-the-badge&logo=socket.io&badgeColor=010101" alt="Socket.io" />
    <img src="https://img.shields.io/badge/ONNX-005CED?style=for-the-badge&logo=onnx&logoColor=white" alt="ONNX Runtime" />
    <img src="https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white" alt="Gemini" />
  </p>
</div>

---

## 📖 Overview

**AutoSplit** is a full-stack, distributed web application engineered to autonomously extract, parse, and allocate financial liabilities from raw receipt imagery. It utilizes a deterministic OCR pipeline backed by ONNX Runtime, paired with Natural Language Processing (NLP) heuristics and Large Language Model (LLM) fallback for edge-case repair.

The architecture is built for **real-time synchronization** across multiple clients, leveraging WebSocket connections for collaborative expense assignment.

---

## 🚀 Key Features & Architecture

### 1. Robust Receipt Parsing Pipeline

- **Deterministic OCR Engine**: Utilizes `rapidocr-onnxruntime` for high-accuracy bounding box detection and text extraction without heavy native system dependencies.
- **Heuristic Line Grouping**: Implements dynamic vertical-overlap clustering to group disparate text tokens into cohesive semantic lines.
- **Intelligent Fallback**: In the event of deterministic parser failure or reconciliation mismatch, the pipeline gracefully falls back to a Gemini-powered LLM refinement layer with strict structured output parsing (`pydantic`).

### 2. NLP-Powered Contextual Entity Resolution

- **SpaCy Integration**: Leverages Named Entity Recognition (NER) to detect names and contextually map them to specific line items.
- **Fuzzy Matching**: Implements `rapidfuzz` for high-tolerance string matching, allowing accurate alignment of assigned items even when OCR output is noisy.

### 3. Distributed State & Synchronization

- **Event-Driven Architecture**: Uses `Flask-SocketIO` to maintain real-time bidirectional communication between the server and all group participants.
- **Conflict Resolution**: Synchronizes granular `ItemAssignment` operations across clients instantly.

### 4. Financial Reconciliation Engine

- **Integrity Validation**: Automatically reconciles parsed line items against detected receipt totals, calculating fractional variations to ensure zero-sum distribution.
- **Deep-linking Integrations**: Exposes pre-filled schema links for UPI and Venmo, alongside programmatic Stripe Payment Intents.

---

## 🧱 Technical Stack

| Domain                  | Technology                | Description                                       |
| ----------------------- | ------------------------- | ------------------------------------------------- |
| **Frontend Framework**  | React 18, Vite            | High-performance client with HMR.                 |
| **Animation & Charts**  | Framer Motion, Recharts   | Fluid layout transitions and data visualization.  |
| **Backend API Server**  | Flask 2.3, Python 3.11    | Lightweight ASGI/WSGI interface.                  |
| **Real-Time Layer**     | Flask-SocketIO, Eventlet  | Asynchronous WebSocket event loops.               |
| **Database ORM**        | SQLAlchemy, Flask-Migrate | Relational data mapping and schema migrations.    |
| **Vision & Extraction** | RapidOCR (ONNX), OpenCV   | Headless document analysis and OCR inference.     |
| **NLP & Intelligence**  | SpaCy, Google GenAI API   | Entity extraction and fallback generative repair. |

---

## 📂 System Topology

```text
autosplit/
├── backend/
│   ├── app.py                 # Application factory & WSGI/ASGI entry point
│   ├── models.py              # Relational schemas (Group, Member, Bill, Item)
│   ├── ocr_parser.py          # Bounding box & text extraction (ONNX)
│   ├── receipt_parser.py      # Deterministic heuristic text parsing
│   ├── intelligent_parser.py  # LLM-assisted structural repair
│   ├── nlp_parser.py          # Named Entity Recognition (SpaCy)
│   ├── reconcile.py           # Integrity and arithmetic validation
│   └── payments.py            # Gateway handlers (Stripe/Venmo/UPI)
│
└── frontend/
    ├── src/
    │   ├── components/        # Isolated, reusable React components
    │   ├── context/           # Global state boundaries
    │   └── utils/             # API clients and WebSocket bindings
    ├── vite.config.js         # Build toolchain configuration
    └── eslint.config.js       # Strict linting ruleset
```

---

## ⚙️ Environment Configuration

The system requires specific environment variables for critical services.

### Backend (`backend/.env`)

```ini
FLASK_ENV=production
FLASK_APP=app.py
SECRET_KEY=cryptographically_secure_string
DATABASE_URL=sqlite:///autosplit.db  # Or PostgreSQL URI
GOOGLE_API_KEY=your_gemini_api_key
STRIPE_SECRET_KEY=optional_stripe_key
STRIPE_PUBLISHABLE_KEY=optional_stripe_pub_key
```

### Frontend (`frontend/.env`)

```ini
VITE_API_BASE_URL=http://localhost:5000/api
```

---

## 🤝 Contributing

Contributions to the parsing heuristics, OCR optimizations, or UI fluidity are highly encouraged. Please adhere to the established ESLint configurations for the frontend and ensure `ruff` linting passes for Python modules before submitting pull requests.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
