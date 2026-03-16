# FastAPI Object Storage Server — MVP Specification

## Project Goal

Build a **single-node object storage server** using **FastAPI** that supports efficient file uploads, downloads, and metadata management.

The project should demonstrate:

* strong **FastAPI and Python proficiency**
* understanding of **async I/O**
* correct **HTTP semantics**
* **storage architecture design**
* ability to **benchmark and evaluate performance**

The system should resemble a **minimal S3-like object store** while remaining implementable in a reasonable amount of time.

---

# High Level System Overview

The system exposes HTTP APIs for:

* bucket management
* object upload
* object download
* object listing
* object deletion

Objects are stored using **content-addressed storage**, meaning files are stored by their **SHA256 hash**.

This enables:

* deduplication
* immutable object storage
* efficient storage management

---

# Storage Architecture

## Directory Layout

```
data/
  objects/
    ab/
      abcd1234hash
  tmp/
  buckets/
```

### objects/

Stores the **actual object data**, indexed by hash.

Objects are stored using the pattern:

```
objects/<first_two_hash_chars>/<full_hash>
```

Example:

```
objects/ab/abcdef123456...
```

This prevents directories from containing too many files.

### tmp/

Temporary upload files are written here during streaming uploads.

Example:

```
tmp/9c0f7a_upload.part
```

### buckets/

Bucket metadata references are stored in the database rather than as files.

---

# Database

The system uses **SQLite** for metadata indexing.

## Table: objects

Stores metadata about unique object blobs.

```
hash TEXT PRIMARY KEY
size INTEGER
created_at TIMESTAMP
```

## Table: keys

Maps bucket keys to object hashes.

```
bucket TEXT
key TEXT
hash TEXT
created_at TIMESTAMP
PRIMARY KEY(bucket, key)
```

## Table: buckets

Stores bucket definitions.

```
name TEXT PRIMARY KEY
created_at TIMESTAMP
```

---

# API Endpoints

## Bucket Management

### Create Bucket

```
PUT /buckets/{bucket}
```

Creates a new bucket.

Requirements:

* bucket names must be unique
* bucket names must be validated

---

### List Buckets

```
GET /buckets
```

Returns all buckets.

Example response:

```json
[
  {"name": "images"},
  {"name": "documents"}
]
```

---

### Delete Bucket

```
DELETE /buckets/{bucket}
```

Requirements:

* bucket must be empty before deletion

---

# Object Upload

### Endpoint

```
PUT /objects/{bucket}/{key}
```

Uploads an object into a bucket.

### Requirements

* Upload must be **streamed**
* The entire file must **not be loaded into memory**
* The SHA256 hash must be **computed during streaming**
* File data must first be written to a **temporary file**

Example streaming pipeline:

```
HTTP request body
        ↓
async stream read
        ↓
tmp/<uuid>.part
        ↓
SHA256 computed
```

After upload completes:

1. The final hash is known
2. The file is moved into the **object store**

---

# Object Download

### Endpoint

```
GET /objects/{bucket}/{key}
```

Returns the object associated with the bucket key.

### Requirements

* Must support **large files**
* Response must use **streaming**
* Must include correct headers:

```
Content-Length
Content-Type
```

---

# HTTP Range Requests

The server must support **partial downloads**.

Example request:

```
GET /objects/{bucket}/{key}
Range: bytes=0-1023
```

### Requirements

The server must:

* return `206 Partial Content`
* include headers:

```
Content-Range
Accept-Ranges
Content-Length
```

Range requests allow efficient downloading of large files.

---

# Object Listing

### Endpoint

```
GET /buckets/{bucket}/objects
```

Returns all objects stored in the bucket.

Example response:

```json
[
  {
    "key": "photo.png",
    "size": 24576,
    "created_at": "2026-03-04T10:00:00"
  }
]
```

---

# Object Deletion

### Endpoint

```
DELETE /objects/{bucket}/{key}
```

Deletes an object reference.

### Requirements

1. Remove key mapping from database
2. If no keys reference the object hash anymore:

   * delete the underlying object file

This ensures **proper garbage collection**.

---

# Content Addressed Storage

Objects are stored by **SHA256 hash**.

Example:

```
objects/ab/abcdef123456...
```

Advantages:

* deduplicates identical files
* ensures immutability
* allows efficient storage reuse

Multiple bucket keys may reference the **same object hash**.

---

# Concurrency and Atomic Write Guarantees

The system must remain correct when **multiple clients upload objects simultaneously**.

## Atomic Write Process

Object creation must be **atomic**.

Workflow:

```
upload stream
     ↓
tmp/<uuid>.part
     ↓
compute SHA256
     ↓
atomic rename
     ↓
objects/<hash>
```

Steps:

1. Stream upload into a **temporary file**
2. Compute SHA256 while streaming
3. After upload completes, move the file to the final location using **atomic rename**

Atomic rename guarantees:

* no partially written files appear in object storage
* readers never see incomplete objects

---

## Concurrent Upload Handling

Two clients may upload the **same file simultaneously**.

Correct behavior:

1. Both uploads compute the same SHA256
2. Both attempt to store the object
3. Only **one upload wins the atomic rename**
4. The other upload detects the object already exists
5. The temporary file is deleted

This guarantees:

* the object exists only once
* no corruption occurs

---

## Database Atomicity

Metadata insertion must also be atomic.

The system must enforce:

* `objects.hash` is **UNIQUE**
* insertion uses **transactions**

Example strategy:

```
INSERT OR IGNORE INTO objects
```

This prevents duplicate object entries.

---

# Benchmark Requirements

The system must support **performance benchmarking**.

Recommended tools:

* wrk
* k6

---

## Upload Benchmark

Example command:

```
wrk -t8 -c200 -d30s http://localhost:8000/objects/test/file
```

---

## Download Benchmark

```
wrk -t8 -c200 -d30s http://localhost:8000/objects/test/file
```

---

## Metrics to Measure

Benchmarks should measure:

* requests per second
* p95 latency
* p99 latency
* throughput (MB/s)

---

# Non-Goals (MVP)

The following features are **out of scope** for the MVP:

* authentication
* distributed storage
* replication
* erasure coding
* multipart uploads
* object versioning
* lifecycle policies

---

# Expected Project Size

Approximate implementation size:

```
1500–2500 lines of code
```

---

# Technologies

* Python
* FastAPI
* asyncio
* SQLite
* hashlib
* uvicorn

---

# Deliverable

A **single-node object storage server** that supports:

* bucket management
* streaming uploads
* streaming downloads
* HTTP range requests
* content-addressed storage
* metadata indexing
* atomic writes
* concurrency-safe uploads
* performance benchmarking
