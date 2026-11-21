# neuro-pipeline

A distributed EEG analysis platform: per-subject signal preprocessing orchestrated
as Kubernetes Jobs, with a Django REST API, PostgreSQL metadata store, S3-compatible
artifact storage, and a React dashboard for visualizing results.

**Status: in progress.** Working today: containerized PostgreSQL and MinIO, the data
model, idempotent dataset ingestion into object storage, and the pipeline stage
framework with dependency validation. The Kubernetes Job orchestration, the
reconciler, the REST API and the React dashboard described below are the target
design and are not built yet. The roadmap at the bottom tracks what is done.

## Overview

Neuroimaging preprocessing is embarrassingly parallel and resource-heavy — each
subject's recording is processed independently, takes minutes of CPU, and produces
artifacts far larger than the metadata describing them. That shape maps naturally
onto Kubernetes Jobs: run-to-completion workloads with explicit resource requests,
retry semantics, and no long-lived process to babysit.

This project treats the neuroscience as the domain and the distributed execution as
the engineering problem. It runs on the public
[PhysioNet EEG Motor Movement/Imagery Database](https://physionet.org/content/eegmmidb/1.0.0/),
so no hardware or private data is required to reproduce it.

## Architecture (target design)

```
                  ┌──────────────┐
   React SPA ────▶│  Django/DRF  │◀──── PostgreSQL (metadata, run state)
                  └──────┬───────┘
                         │ writes manifest, creates Jobs via k8s API
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

Three design decisions drive the rest of the system.

**Job status is reconciled, not reported.** A pipeline pod does not call back into
the API when it finishes. A reconciliation loop continuously compares desired state
(`PipelineRun` rows) against actual state (Job objects from the Kubernetes API) and
drives them together. This is level-triggered rather than edge-triggered: a pod that
is OOM-killed, evicted, or lost with its node still converges to a correct terminal
state, whereas a completion callback would simply never fire and leave the run stuck
in `RUNNING` forever.

**Pipeline containers never touch the database.** A job is given a run ID and a
subject; everything else it needs comes from a manifest in object storage. It reads
inputs from object storage, writes outputs and a results manifest back, and exits
with a status code. Database credentials never reach workload pods, and the
preprocessing code is testable against a local directory with no services running.

**The web image and the pipeline image are built separately.** They share no
dependency file. The API container has no numerical computing stack, the pipeline
container has no web framework, and the boundary between them is enforced by what is
installed rather than by convention.

## Pipeline design

A pipeline is a list of `Stage` objects, each declaring the context keys it
`requires` and `produces`. The list is validated at construction, so a misordered
pipeline fails immediately with a message naming the unsatisfied dependency rather
than raising `KeyError` several minutes into a container run.

```python
Pipeline([
    FetchInputsStage(store),   # produces: input_paths
    ReadRawStage(),            # requires: input_paths   produces: raw
    FilterStage(),             # requires: raw           produces: raw_filtered
    EpochStage(),              # requires: raw_filtered  produces: epochs, labels
])
```

Because the pipeline is data rather than control flow, supporting a second modality
means constructing a different list — not branching inside existing stages.

Stages communicate through a `PipelineContext` carrying two deliberately separate
dictionaries: `data` for bulky in-memory objects that die with the process, and
`metrics` for small values that are serialized to `results.json` and ingested into
Postgres. Per-stage timings are collected automatically.

### Job manifest

Django writes a manifest to object storage before creating a Job:

```json
{
  "run_id": 7,
  "subject": "S001",
  "dataset": "eegmmidb",
  "pipeline_version": "0.1.0",
  "params": {"l_freq": 8.0, "h_freq": 30.0},
  "inputs": [
    {"key": "raw/eegmmidb/S001/S001R04.edf", "external_id": "S001R04"}
  ]
}
```

This keeps the pipeline dataset-agnostic — it fetches keys it is told about rather
than reconstructing filenames from dataset-specific conventions — and leaves a
permanent record of exactly what each job was asked to do.

## Stack

| Layer | Technology |
|---|---|
| API | Django 5.2 LTS, Django REST Framework |
| Database | PostgreSQL 17 |
| Object storage | MinIO (S3-compatible) |
| Signal processing | MNE-Python, NumPy, SciPy (stages in progress) |
| Orchestration | Kubernetes Jobs, official Python client (planned) |
| Containerization | Docker, Docker Compose for local services |
| Frontend | React + Vite (planned) |
| CI | GitHub Actions (planned) |

## Local development

**Requirements:** Docker Desktop, Python 3.12, Node 20+.

```bash
git clone https://github.com/pranitdeshpande98/Neuro-Pipeline.git
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

# Database and object storage
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py init_storage

# Ingest data (~150 MB, a few minutes)
python manage.py ingest_eegmmidb --subjects 20

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

## Data

[EEG Motor Movement/Imagery Database](https://physionet.org/content/eegmmidb/1.0.0/)
(Schalk et al., 2004), distributed by PhysioNet. 109 subjects, 64 channels, 160 Hz.
No data is committed to this repository.

Each subject has 14 runs. This project ingests **R04, R08 and R12** — the three
repetitions of *imagined* left-or-right fist movement, annotated `T1` (left fist
onset) and `T2` (right fist onset), with `T0` as rest. That gives a clean binary
classification target.

Six subjects — **S038, S088, S089, S092, S100, S104** — have known annotation errors
and are excluded, consistent with published use of this dataset. The exclusion is
encoded in the ingestion command rather than left to surface as downstream failures.

### Object storage layout

```
raw/{dataset}/{subject}/{recording}.edf
runs/{run_id}/{subject}/manifest.json
derived/{run_id}/{subject}/{name}.npz
results/{run_id}/{subject}/results.json
models/{model_version}/weights.pt
```

Prefixes run coarsest to finest so that "everything for run 7" and "everything
derived, ever" are single prefix listings. It also allows a lifecycle policy to
expire `derived/` while retaining `raw/` — which matches the actual cost structure,
since raw data is irreplaceable and derived data is regenerable.

Ingestion is idempotent at three independent layers: a local download cache, an
object-existence check, and an `ingested_at` timestamp, with SHA-256 checksums
recorded per recording. Re-running it is a no-op.

## Project structure

```
backend/            Django project
  config/           Settings, root URLs, WSGI
  apps/
    catalog/        Datasets, subjects, recordings, ingestion commands
    runs/           Pipeline runs, Job orchestration, reconciler
    ml/             Model versions and predictions
    common/         S3 client, EDF header parsing
pipeline/           Standalone preprocessing package (imports no Django)
  stages/           Individual pipeline stages
frontend/           React dashboard
deploy/
  docker/           Dockerfiles
  k8s/              Kubernetes manifests
```

## Design notes

**Deliberate duplication.** `pipeline/storage.py` duplicates the S3 client in
`backend/apps/common/storage.py`. The two packages ship as separate images with
separate dependency sets and neither may import the other; ~50 lines of duplication
is the price of that boundary. A shared installable package is the alternative and
would be the right call at larger scale.

**No MNE in the web image.** Ingestion needs channel count, sampling rate and
duration, which would ordinarily mean `mne.io.read_raw_edf`. Instead
`backend/apps/common/edf.py` parses the EDF header directly — about 25 lines of
standard library code — so the web image keeps no numerical computing stack.

**One denormalized field, one writer.** `PipelineRun.status` is derivable from its
jobs but stored, because the dashboard lists runs and computing status per row means
an aggregate query per row. Only the reconciler writes it.

**`on_delete` chosen per relationship.** Deleting a dataset that still has subjects
fails loudly (`PROTECT`); deleting a subject removes its recordings (`CASCADE`).

## Roadmap

- [x] Project scaffold, containerized Postgres and MinIO, environment-based config
- [x] Schema: datasets, subjects, recordings, pipeline runs, subject jobs, artifacts
- [x] Idempotent dataset ingestion into object storage
- [x] Pipeline stage framework with dependency validation
- [ ] MNE preprocessing stages (filter, epoch, artifact rejection)
- [ ] Results manifest and job runner entrypoint
- [ ] Pipeline Docker image
- [ ] Kubernetes Job orchestration and status reconciliation
- [ ] REST API
- [ ] React dashboard
- [ ] EEGNet classifier for motor imagery, trained as a Job
- [ ] LLM-generated run summaries, grounded in stored metrics
- [ ] GitHub Actions CI