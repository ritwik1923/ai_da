┌─────────────────────────────────────────────────────────────────────────┐
│                          Client Layer (Web)                             │
│  ┌─────────────────┐                                                    │
│  │ React Frontend  │ (Hosted statically on Vercel / S3 + CloudFront)    │
│  └───────┬─────────┘                                                    │
└──────────┼──────────────────────────────────────────────────────────────┘
           │ HTTPS
┌──────────▼──────────────────────────────────────────────────────────────┐
│                    CDN & Load Balancing Layer                           │
│  ┌─────────────────────────────┐                                        │
│  │ Cloudflare / AWS CloudFront │ (WAF, DDoS Protection, Static Cache)   │
│  └─────────────┬───────────────┘                                        │
│                │                                                        │
│  ┌─────────────▼───────────────┐                                        │
│  │ Application Load Balancer   │ (Distributes traffic, terminates SSL)  │
│  └─────────────┬───────────────┘                                        │
└────────────────┼────────────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────────────────┐
│                API & Compute Layer (Dockerized)                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ FastAPI Web Servers (Google Cloud Run / AWS ECS) - Scaled Out   │    │
│  │ • Auth & Validation                                             │    │
│  │ • /api/files (Generates Presigned S3 URLs for direct upload)    │    │
│  │ • /api/chat (Hands off tasks to broker, returns Task ID)        │    │
│  └─────┬──────────────────────────┬──────────────────────────┬─────┘    │
│        │                          │                          │          │
│  ┌─────▼─────────────────┐  ┌─────▼─────────────────┐  ┌─────▼───────┐  │
│  │ Managed PostgreSQL DB │  │ Managed Redis Cache   │  │ Task Broker │  │
│  │ (Metadata, Users,     │  │ (Session State, Agent │  │ (Redis or   │  │
│  │  Pointers to Files)   │  │  Memory, Rate Limits) │  │  RabbitMQ)  │  │
│  └───────────────────────┘  └───────────────────────┘  └─────┬───────┘  │
└──────────────────────────────────────────────────────────────┼──────────┘
                                                               │
┌──────────────────────────────────────────────────────────────▼──────────┐
│             Asynchronous Processing & AI Layer (Dockerized)             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Celery Background Workers                                       │    │
│  │ • Initializes DataAnalystAgent with Redis memory                │    │
│  │ • Orchestrates LLM calls (OpenAI API)                           │    │
│  └─────┬──────────────────────────┬────────────────────────────────┘    │
│        │                          │                                     │
│  ┌─────▼─────────────────┐  ┌─────▼────────────────────────────────┐    │
│  │ S3 / GCS Storage      │  │ Sandboxed Execution Environment      │    │
│  │ • Uploaded Datasets   │  │ (AWS Lambda / gVisor Containers)     │    │
│  │ • Generated Charts    │  │ • Executes generated Pandas code     │    │
│  │                       │  │ • Network-isolated, strict timeouts  │    │
│  └───────────────────────┘  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘