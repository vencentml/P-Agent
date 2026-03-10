# Personal Exocortex Agent (Phase 0 / Step 1)

This repository currently implements **Step 1: 环境与感知（只读）** from the PRD:

- Docker Compose for local Neo4j infrastructure
- A Python incremental polling script that reads OCR/Audio text from a local Screenpipe instance every minute and prints results

## Structure

```text
exocortex-agent/
├── data_ingestion/
│   └── screenpipe_incremental_pull.py
└── docker/
    └── docker-compose.yml
```

## 1) Start Neo4j

```bash
cd exocortex-agent/docker
docker compose up -d
```

Neo4j endpoints:
- Browser: `http://localhost:7474`
- Bolt: `bolt://localhost:7687`
- Default auth: `neo4j / neo4j_dev_password`

## 2) Run Screenpipe incremental pull script

```bash
cd exocortex-agent
python3 data_ingestion/screenpipe_incremental_pull.py \
  --base-url http://127.0.0.1:3030 \
  --interval-seconds 60
```

Useful options:
- `--once`: run a single poll and exit
- `--start-since <ISO_TIME>`: start from a specific cursor timestamp
- `--source-types ocr,audio`: override source types
