# R26-SE-013 - A Centralized System for Real-Time Animal Farm Reporting

Welcome to the central repository for the **Real-Time Animal Farm Reporting System**. This platform transitions livestock management from a reactive crisis response to a proactive, data-driven paradigm. Built for unconstrained farm environments, the system empowers field officers with clinical-grade remote triage, real-time tracking, and predictive decision-support.

## 💻 Tech Stack
This project utilizes a streamlined, high-performance architecture optimized for deep learning inference and real-time user interaction:
*   **Backend & AI Inference:** FastAPI (Python)
*   **Frontend User Interface:** React.js (Vite) + Tailwind CSS
*   **Database:** MongoDB Atlas

---

## 📂 Project Structure

To maintain clean code and prevent merge conflicts, the repository is split into `backend` and `frontend`. Inside each, the architecture is divided by our four core research domains. 

```text
Animal-Farm-Reporting/
│
├── backend/                       # FastAPI & Python AI Inference
│   ├── main.py                    # Application entry point & server config
│   ├── requirements.txt           # Python dependencies (fastapi, ultralytics, etc.)
│   ├── core/                      # MongoDB connection and global settings
│   ├── shared/                    # Shared utility functions and models
│   └── components/                # 🔬 The 4 Research Components (Backend Logic)
│       ├── smart_diagnostics/     # Tiered Computer Vision & Prognostics 
│       ├── geospatial_tracking/   # Spatial Clustering & Trajectory Mapping
│       ├── risk_forecasting/      # Time-Series & Climate-Informed Forecasting
│       └── health_anomaly/        # Automated Body Condition Scoring (BCS)
│
├── frontend/                      # React.js, Vite & Tailwind CSS
│   ├── package.json               # Node dependencies
│   ├── vite.config.js             # Vite development environment configuration
│   ├── tailwind.config.js         # Tailwind utility styling configuration
│   ├── public/                    # Static assets (Logos, icons)
│   └── src/
│       ├── App.jsx                # Main React router
│       ├── main.jsx               # React DOM rendering
│       ├── shared_components/     # Reusable UI (Navbars, Buttons, Loaders)
│       ├── services/              # Axios API calls to the FastAPI backend
│       └── features/              # 🔬 The 4 Research Components (Frontend UI)
│           ├── SmartDiagnostics/  # Image Upload UI & CoT Report Views
│           ├── GeospatialMap/     # Interactive Heatmaps & Tracking UI
│           ├── RiskForecasting/   # Predictive Charts & Risk Index Dashboards
│           └── HealthAnomaly/     # Farmer Wellness Dashboards
│
├── .gitignore                     # Ignores node_modules, __pycache__, and .env files
└── README.md                      # Project documentation
```

---

## 🔬 Research Components & Team

This platform is driven by four integrated research modules, developed concurrently:

1.  **Animal Health Anomaly Detection:** Focuses on early physiological distress by automating Body Condition Scoring (BCS) through 2D mobile vision. *(W.M.P.J Wijenayake)*
2.  **AI-Powered Smart Diagnosis:** A 4-tier computer vision pipeline utilizing YOLOv8 and Swin Transformers for multi-label disease detection and severity quantification. *(Lead: A.L.M Athulathmudali)*
3.  **Real-Time Geospatial Clustering:** Ingests diagnostic payloads to map localized outbreak velocities and predict infectious trajectories. *(G.A Sandaru)*
4.  **Time-Series Risk Forecasting:** Integrates historical outbreak data with monsoon patterns to forecast sudden outbreak spikes. *(S.S Kumarasinghe)*

---

## 🚀 Local Development Setup

Follow these steps to run the application locally on your machine.

### Prerequisites
*   Node.js (v18+)
*   Python (3.10+)
*   MongoDB Atlas Account (or local MongoDB Compass)

### 1. Backend Setup (FastAPI)
Open a terminal and navigate to the `backend` directory:
```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server (Runs on http://localhost:8000)
uvicorn main:app --reload
```
*Note: You can view the interactive API documentation at `http://localhost:8000/docs`.*

### 2. Frontend Setup (React/Vite)
Open a **new** terminal and navigate to the `frontend` directory:
```bash
cd frontend

# Install dependencies
npm install

# Start the Vite development server (Runs on http://localhost:5173)
npm run dev
```

### 3. Environment Variables
You will need to create a `.env` file in both the `backend` and `frontend` folders.
*   **Backend `.env`:** Needs your `MONGO_URI` connection string.
*   **Frontend `.env`:** Needs the `VITE_API_URL` pointing to your local FastAPI server (`http://localhost:8000`).


