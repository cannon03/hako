# Hako 📦 | High-Performance Object Storage Server

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)
![SQLite](https://img.shields.io/badge/SQLite-Asyncio-003B57.svg)

**Hako** is a high-performance, single-node object storage server built with Python and FastAPI. Designed as a minimal S3-clone, it provides efficient file uploads, downloads, and bucket management. 

At its core, Hako utilizes a **Content-Addressed Storage (CAS)** architecture, async disk I/O, and atomic writes to guarantee data integrity, aggressive deduplication, and safe concurrent workloads without exhausting system memory.

## 🧠 System Architecture & Design Decisions

### 1. Content-Addressed Storage (CAS) & Deduplication
Instead of storing files by their location path, Hako stores files by their **SHA-256 hash**. 
* **Zero Duplication:** If 1,000 users upload the exact same 50MB video to different buckets, the server only writes the file to disk *once*, drastically reducing storage costs.
* **Smart Garbage Collection:** Deleting a file removes its key reference. The underlying physical file is only deleted if a database check confirms no other keys are currently referencing that hash.

### 2. Zero-Memory Streaming Pipeline
Handling large files (e.g., 50GB+) on a web server traditionally risks Out-Of-Memory (OOM) crashes.
* **Uploads:** Requests are streamed in chunks and written directly to a temporary file via `aiofiles`, while the SHA-256 hash is computed on the fly.
* **Downloads:** Served via FastAPI's `StreamingResponse` combined with asynchronous generator functions, ensuring RAM usage remains flat regardless of file size.

### 3. Concurrency & Atomic Writes
Hako is designed to handle multiple users uploading identical files simultaneously without data corruption or database deadlocks.
* **Atomic Renames:** Uploaded chunks are written to `/tmp`. Only after the upload is complete and the hash is verified is the file moved to its final CAS destination using POSIX atomic renames (`os.replace`).
* **Database Locks:** Uses SQLAlchemy's SQLite dialect for `INSERT OR IGNORE` (objects table) and `INSERT OR REPLACE` (keys table) to resolve race conditions at the database layer.

### 4. Advanced HTTP Semantics
Hako strictly adheres to HTTP standards to support modern client behaviors.
* **Resumable Downloads & Video Scrubbing:** Fully implements parsing for the `Range: bytes=X-Y` header, returning `206 Partial Content` with accurate `Content-Range` and `Content-Length` headers.

### 5. High-Performance Non-Blocking Logging
Utilizes **Loguru** for structured application logging. The logger is configured with `enqueue=True`, shifting I/O operations to a background thread to prevent disk/terminal writes from blocking FastAPI's async event loop under heavy load.

---

## 📊 Performance Benchmarks

Hako was load-tested using `wrk` on a standard consumer laptop (simulating 8 threads and 200 concurrent connections over 30 seconds for a 1MB payload).

* **Throughput:** ~615+ MB/s
* **Requests Per Second (RPS):** ~615+ 
* **Latency (p50):** ~302ms
* **Concurrency:** Flawlessly handled 200 simultaneous connections with near-zero socket timeouts (1 timeout out of 18,500+ requests) when utilizing Docker's dynamic `$(nproc)` Uvicorn worker scaling and non-blocking background logging.

---

## 🛠️ Tech Stack

* **Framework:** FastAPI
* **Database:** SQLite (via `aiosqlite`)
* **ORM:** SQLAlchemy 2.0 (AsyncSession)
* **Data Validation:** Pydantic
* **Async I/O:** `aiofiles`, `asyncio`
* **Logging:** Loguru
* **Containerization:** Docker & Docker Compose

---

## 🚀 Getting Started

The easiest way to run Hako is via Docker. The application is configured to automatically scale its worker processes to match your host machine's CPU cores.

### Prerequisites
* Docker & Docker Compose installed.

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/yourusername/hako-storage.git](https://github.com/yourusername/hako-storage.git)
   cd hako-storage 
   
   ```

2. Start the server:
    ```bash
    docker-compose up -d --build
    ```

The API will instantly be available at http://localhost:8000. Persistent storage (SQLite DB and the CAS objects) is safely mounted to the local ./data directory.

---


### Part 3: API Reference & Testing


## 📖 API Reference

You can view the interactive OpenAPI documentation by visiting `http://localhost:8000/docs` while the server is running.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `PUT` | `/buckets/{bucket}` | Create a new bucket. |
| `GET` | `/buckets` | List all buckets. |
| `DELETE` | `/buckets/{bucket}` | Delete a bucket (must be empty). |
| `PUT` | `/objects/{bucket}/{key:path}` | Stream an upload and compute its CAS hash. |
| `GET` | `/objects/{bucket}/{key:path}` | Download an object (Supports HTTP Range requests). |
| `GET` | `/objects/{bucket}/objects` | List all objects within a specific bucket. |
| `DELETE` | `/objects/{bucket}/{key:path}` | Delete a key and trigger Garbage Collection. |

---

## 🧪 Testing

Hako includes a comprehensive integration test suite using `pytest` and `httpx`.

To run the tests locally (requires a Python virtual environment):
```bash
pip install -r requirements.txt
pip install pytest httpx
pytest tests/
```