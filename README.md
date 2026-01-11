<p align="center">
  <img src="https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

<h1 align="center">🤖 Autonomous AI-powered SRE Agent</h1>

<p align="center">
  <strong>Self-Healing CI/CD Platform that detects failures, diagnoses root causes, and auto-generates safe fixes</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/🚧-Under%20Active%20Development-yellow?style=flat-square" alt="Development Status">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-whats-new">What's New</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🚧 Project Status

> ⚠️ **This project is currently under active development.** Features may be incomplete or subject to change. Contributions and feedback are welcome!

---

## 🌟 Overview

The **Autonomous AI-powered SRE Agent** is a cutting-edge platform that revolutionizes how engineering teams handle CI/CD failures. Instead of manually debugging build failures, our AI agent:

- 🔍 **Detects** CI/CD failures in real-time via GitHub webhooks
- 🧠 **Diagnoses** root causes using AI-powered analysis
- 🔧 **Generates** safe, context-aware code fixes using LLMs
- ✅ **Validates** fixes in isolated sandbox environments
- 🚀 **Creates** Pull Requests with detailed explanations

> **No more 3 AM debugging sessions. Let the AI agent fix your builds while you sleep.**

---

## 🆕 What's New

### 🖥️ React Dashboard (NEW!)
- Modern React 18 + TypeScript frontend
- Real-time system overview and metrics
- Interactive event monitoring and management
- Responsive design with dark mode support

### 🔐 User Authentication & Authorization (NEW!)
- JWT-based secure authentication
- User registration and login system
- Role-based access control (RBAC)
- Session management with Redis

### 🔔 Real-time Notifications (NEW!)
- Server-Sent Events (SSE) for instant updates
- In-app notification center
- Configurable alert preferences
- Push notification support

### 📊 Dashboard API (NEW!)
- System health metrics endpoint
- Event statistics and analytics
- User management interface
- Real-time data streaming

### 📝 Audit Logging (NEW!)
- Comprehensive activity tracking
- User action history
- Security event monitoring
- Compliance-ready logging

---

## ✨ Core Features

### 🎯 Intelligent Failure Detection
- Real-time GitHub webhook integration
- Automatic failure event ingestion
- Multi-runner support (GitHub Actions, CircleCI, Jenkins)

### 🧪 AI-Powered Root Cause Analysis
- Semantic log analysis with ML models
- Pattern matching against known failure signatures
- Contextual understanding of build configurations

### 🛠️ Autonomous Fix Generation
- LLM-powered code fix suggestions
- Multi-file fix support with line-level precision
- Safe, reversible modifications only

### 🏖️ Sandbox Validation
- Isolated Docker environments for fix testing
- Automated test execution pre-merge
- Rollback-safe architecture

### 📋 Smart PR Management
- Auto-generated PRs with detailed changelogs
- Confidence scores for each fix
- One-click approval or rejection

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  GitHub/CI/CD   │────▶│  Event Ingestion │────▶│  Failure Store  │
│    Webhooks     │     │       API        │     │   (PostgreSQL)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PR Creation   │◀────│   AI Fix Engine  │◀────│  Intelligence   │
│    Service      │     │  (LLM + Context) │     │     Layer       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         │              ┌────────▼────────┐
         │              │  Sandbox Engine │
         │              │  (Validation)   │
         │              └─────────────────┘
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Repository                            │
│              (Auto-generated Pull Requests)                     │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| **API Framework** | FastAPI (async) |
| **Task Queue** | Celery + Redis |
| **Database** | PostgreSQL (async) |
| **LLM Provider** | Ollama (DeepSeek Coder) |
| **ML/Embeddings** | Sentence Transformers + FAISS |
| **Observability** | OpenTelemetry |
| **Containerization** | Docker + Docker Compose |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **Poetry** (Python package manager)
- **GitHub Personal Access Token** (for API access)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/Mrgig7/Autonomous-Al-powered-SRE-Agent.git
cd Autonomous-Al-powered-SRE-Agent

# Configure environment
cp .env.example .env
# Edit .env with your GitHub token and other settings

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

The API will be available at `http://localhost:8000`

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/Mrgig7/Autonomous-Al-powered-SRE-Agent.git
cd Autonomous-Al-powered-SRE-Agent

# Configure environment
cp .env.example .env

# Start infrastructure services
docker-compose up -d postgres redis

# Install dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Start the API server (Terminal 1)
poetry run uvicorn sre_agent.main:app --reload --host 0.0.0.0 --port 8000

# Start the Celery worker (Terminal 2)
poetry run celery -A sre_agent.celery_app worker --loglevel=info
```

---

## 🔌 API Reference

### Health Check
```http
GET /health
```

### Ingest CI/CD Event
```http
POST /api/v1/events/ingest
Content-Type: application/json

{
  "event_type": "workflow_run",
  "repository": "owner/repo",
  "run_id": 12345,
  "status": "failure",
  "logs_url": "https://api.github.com/..."
}
```

### Get Failure Analysis
```http
GET /api/v1/failures/{failure_id}/analysis
```

### Generate Fix
```http
POST /api/v1/failures/{failure_id}/fix
```

📖 **Full API documentation available at:** `http://localhost:8000/docs`

---

## ⚙️ Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Required |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature secret | Required |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `LLM_PROVIDER` | LLM provider (ollama) | `ollama` |
| `OLLAMA_MODEL` | Model for fix generation | `deepseek-coder:6.7b` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=src/sre_agent --cov-report=html

# Run specific test file
poetry run pytest tests/test_api.py -v
```

---

## � Project Structure

```
.
├── src/sre_agent/          # Main application package
│   ├── ai/                 # AI/LLM integration modules
│   ├── api/                # FastAPI routes and endpoints
│   ├── core/               # Core utilities and configs
│   ├── intelligence/       # Failure analysis engine
│   ├── knowledge/          # Knowledge base and embeddings
│   ├── models/             # SQLAlchemy database models
│   ├── pr/                 # Pull request creation service
│   ├── sandbox/            # Sandbox validation engine
│   ├── schemas/            # Pydantic request/response models
│   ├── services/           # Business logic services
│   └── tasks/              # Celery async tasks
├── tests/                  # Test suite
├── alembic/                # Database migrations
├── docker-compose.yml      # Docker orchestration
├── Dockerfile              # Container build instructions
└── pyproject.toml          # Project dependencies
```

---

## 🗺️ Roadmap

### ✅ Completed
- [x] 🏗️ Project foundation & architecture
- [x] 📡 Event ingestion API
- [x] 🧠 AI fix generation engine
- [x] 🏖️ Sandbox validation engine
- [x] 📋 PR creation service
- [x] 🌐 React Dashboard (Web UI)
- [x] 🔐 User Authentication & Authorization
- [x] 🔔 Real-time Notifications (SSE)
- [x] 📊 Dashboard API & Analytics
- [x] 📝 Audit Logging System

### 🚧 In Progress
- [ ] 🔄 Multi-CI/CD platform support (CircleCI, GitLab)
- [ ] � Advanced Analytics & Reporting
- [ ] � Enhanced Security Features

### 🔮 Planned
- [ ] 📱 Mobile-responsive PWA
- [ ] 🤖 AI Model Fine-tuning
- [ ] � Multi-region Deployment Support
- [ ] 📊 Custom Dashboard Widgets

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with ❤️ for SRE teams everywhere</strong>
</p>

<p align="center">
  <a href="https://github.com/Mrgig7/Autonomous-Al-powered-SRE-Agent/issues">Report Bug</a> •
  <a href="https://github.com/Mrgig7/Autonomous-Al-powered-SRE-Agent/issues">Request Feature</a>
</p>
