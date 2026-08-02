# neuro-pipeline

A distributed EEG analysis platform: per-subject signal preprocessing orchestrated
as Kubernetes Jobs, with a Django REST API, PostgreSQL metadata store, S3-compatible
artifact storage, and a React dashboard for visualizing results.

**Status:** in active development. See the roadmap below.

## Overview

Neuroimaging preprocessing is embarrassingly parallel and resource-heavy — each
subject's recording is processed independently, takes minutes of CPU, and produces
artifacts far larger than the metadata describing them. That shape maps naturally
onto Kubernetes Jobs: run-to-completion workloads with explicit resource requests,
retry semantics, and no long-lived process to babysit.

This project treats the neuroscience as the domain and the distributed execution as
the engineering problem. The pipeline runs on the public
[PhysioNet EEG Motor Movement/Imagery Database](https://physionet.org/content/eegmmidb/1.0.0/),
so no hardware or private data is required to reproduce it.

## Architecture

```
                  ┌──────────────┐
   React SPA ────▶│  Django/DRF  │◀──── PostgreSQL (metadata, run state)
                  └──────┬───────┘
                         │ creates Jobs via k8s API
                         ▼
                  ┌──────────────┐
                  │  K8s Jobs    │──────▶ MinIO / S3 (raw + derived artifacts)
                  │ (1/subject)  │
                  └──────┬───────┘
                         │ observed by
                         ▼
                  ┌──────────────┐
                  │  Reconciler  │──────▶ PostgreSQL (run status)
                  └──────────────┘
```

Three design decisions drive the rest of the system:

**Job status is reconciled, not reported.** A pipeline pod does not call back into
the API when it finishes. Instead a reconciliation loop continuously compares
desired state (`PipelineRun` rows) against actual state (Job objects from the
Kubernetes API) and drives them together. This is level-triggered rather than
edge-triggered: a pod that is OOM-killed, evicted, or lost with its node still
converges to a correct terminal state, whereas a completion callback would simply
never fire and leave the run stuck in `RUNNING` forever.

**Pipeline containers never touch the database.** They read inputs from object
storage, write outputs and a results manifest back to object storage, and exit with
a status code. Database credentials therefore never reach the workload pods, and the
preprocessing code is testable against a local directory with no services running.

**The web image and the pipeline image are built separately.** They share no
dependency file. The API container has no numerical computing stack, the pipeline
container has no web framework, and the architectural boundary between them is
enforced by what is installed rather than by convention.

## Stack

| Layer | Technology |
|---|---|
| API | Django 5.2 LTS, Django REST Framework |
| Database | PostgreSQL 17 |
| Object storage | MinIO (S3-compatible) |
| Signal processing | MNE-Python, NumPy, SciPy |
| Orchestration | Kubernetes Jobs, official Python client |
| Containerization | Docker, Docker Compose for local services |
| Frontend | React + Vite |
| CI | GitHub Actions |

## Local development

**Requirements:** Docker Desktop, Python 3.12, Node 20+.

```bash
git clone https://github.com/<username>/neuro-pipeline.git
cd neuro-pipeline

# Configuration
cp .env.example .env
# Generate a secret key and set DJANGO_SECRET_KEY:
#   python -c "import secrets; print(secrets.token_urlsafe(64))"

# Backing services
docker compose up -d

# Python environment
py -3.12 -m venv .venv          # Windows
source .venv/bin/activate       # or .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Database
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

| Service | URL |
|---|---|
| API / admin | http://localhost:8000/admin |
| MinIO console | http://localhost:9001 |
| PostgreSQL | localhost:5433 |

Postgres is published on host port **5433**, not 5432, to avoid colliding with a
natively installed PostgreSQL service. The container still listens on 5432
internally, so nothing changes in the Kubernetes deployment.

Use `secrets.token_urlsafe` rather than Django's `get_random_secret_key` for the
secret key: the latter draws from an alphabet including `$` and `#`, which break
Docker Compose variable interpolation and `.env` comment parsing respectively.

## Project structure

```
backend/            Django project
  config/           Settings, root URLs, WSGI
  apps/
    catalog/        Subjects and recordings
    runs/           Pipeline runs, Job orchestration, reconciler
    ml/             Model versions and predictions
pipeline/           Standalone preprocessing package (imports no Django)
frontend/           React dashboard
deploy/
  docker/           Dockerfiles
  k8s/              Kubernetes manifests
```

## Roadmap

- [x] Project scaffold, containerized Postgres and MinIO, environment-based config
- [ ] Schema: subjects, recordings, pipeline runs, artifacts
- [ ] Dataset ingestion into object storage
- [ ] MNE preprocessing pipeline (filter, epoch, artifact rejection)
- [ ] Kubernetes Job orchestration and status reconciliation
- [ ] REST API
- [ ] React dashboard
- [ ] EEGNet classifier for motor imagery, trained as a Job
- [ ] LLM-generated run summaries, grounded in stored metrics
- [ ] GitHub Actions CI

## Data

[EEG Motor Movement/Imagery Database](https://physionet.org/content/eegmmidb/1.0.0/)
(Schalk et al., 2004), distributed by PhysioNet under the Open Data Commons
Attribution License. 109 subjects, 64-channel recordings at 160 Hz. No data is
committed to this repository.