# JP_log_AI

## Real-time Log Anomaly Detection with LLM-powered Root Cause Analysis

JP_log_AI is a robust and scalable system designed for real-time anomaly detection in log streams. It leverages a combination of log parsing (Drain3), unsupervised anomaly detection (RRCF), and large language models (LLMs) for in-depth root cause analysis. When an anomaly is detected, it not only flags the event but also sends a detailed analysis to a Google Chat space.

## Features

-   **Real-time Log Ingestion**: Listens for incoming log streams over TCP.
-   **Log Parsing with Drain3**: Automatically extracts log templates and identifies event IDs for structured analysis.
-   **Anomaly Detection with RRCF**: Utilizes the Robust Random Cut Forest (RRCF) algorithm to detect deviations from normal log patterns.
-   **LLM-powered Root Cause Analysis**: When an anomaly is detected, the last 10 log lines are sent to a local LLM (Qwen/Qwen2.5-1.5B-Instruct) for immediate root cause analysis.
-   **Multithreaded Architecture**: Employs a producer-consumer pattern with multiple threads for efficient, non-blocking processing of log ingestion, anomaly detection, and LLM analysis.
-   **Google Chat Integration**: Sends anomaly alerts and LLM analysis directly to a configured Google Chat space.
-   **Warm-up Phase**: Initializes the anomaly detection model with historical log data to establish a baseline.
-   **Scalable**: Designed to handle high-throughput log streams by distributing computational load across multiple CPU cores for RRCF and using queues for sequential LLM processing.

## Architecture Overview

The system operates with a multi-threaded design:

1.  **Main Thread**: Responsible for accepting new client connections.
2.  **Client Handler Threads**: For each connected client, a dedicated thread reads incoming log data and places individual log lines into a `log_queue`.
3.  **Log Processor Thread**: A single worker thread continuously pulls log lines from the `log_queue`, processes them through Drain3 and RRCF, and detects anomalies.
4.  **LLM Analysis Worker Thread**: When an anomaly is detected, a snapshot of recent logs is placed into an `llm_analysis_queue`. A dedicated worker thread processes these requests sequentially, calling the LLM for analysis and sending the results to Google Chat.
5.  **RRCF Multiprocessing**: The RRCF model itself uses `multiprocessing` to distribute the anomaly scoring across multiple CPU cores for performance.

## Setup and Installation

### Prerequisites

-   Python 3.8+
-   `pip` (Python package installer)
-   `git` (for cloning the repository)
-   A local LLM model (Qwen/Qwen2.5-1.5B-Instruct)

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/Jakub_log_AI.git
cd Jakub_log_AI
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download LLM Model

The `LLM/llm.py` script uses `Qwen/Qwen2.5-1.5B-Instruct`. The `transformers` library will automatically download this model the first time it's initialized. Ensure you have sufficient disk space (several GBs) and RAM (at least 8GB, preferably more for the LLM).

### 4. Configure Google Chat API

Create a `.env` file in the root directory of the project (`AI_log_agent/`) and add your Google Chat Webhook URL:

```
api_url="YOUR_GOOGLE_CHAT_WEBHOOK_URL_HERE"
```

You can obtain a webhook URL by configuring a new incoming webhook in your Google Chat space.

## Usage

### 1. Start the Anomaly Detection Server

Run the main script:

```bash
python auto_log_flagger.py
```

The server will first perform a warm-up phase using the `HISTORICAL_FILE` and then start listening for live TCP streams on `127.0.0.1:1010`.

### 2. Send Logs (ONLY FOR TESTING)

Use the `log_sender.py` script to stream logs to the anomaly detection server.

```bash
python log_sender.py
```

You can modify `log_sender.py` to point to different log files or adjust the `DELAY` between sending lines.

## Configuration

Key configuration parameters can be found and modified in `auto_log_flagger.py` and `ML/rrcf.py`:

### `auto_log_flagger.py`

-   `HOST`: The IP address the server binds to (default: `127.0.0.1`).
-   `PORT`: The port the server listens on (default: `1010`).
-   `HISTORICAL_FILE`: Path to the log file used for the warm-up phase.
-   `MAX_WARMUP_LINES`: Number of lines to process during warm-up.
-   `recent_logs_deque`: Max length of the deque storing recent logs for LLM context (default: `10`).

### `ML/rrcf.py`

-   `SHINGLE_SIZE`: The size of the log shingle (sequence of event IDs).
-   `TREE_SIZE`: The maximum size of each RRCF tree.
-   `NUM_TREES`: The total number of trees in the RRCF forest.
-   `THRESHOLD`: The anomaly score threshold for flagging an alert.
-   `CORES_TO_USE`: Number of CPU cores to utilize for RRCF processing.

## Graceful Shutdown

To gracefully shut down the `auto_log_flagger.py` server, press `Ctrl+C`. The system will clean up its multiprocessing cores and worker threads before exiting.

## Project Structure

```
AI_log_agent/
├── auto_log_flagger.py         # Main anomaly detection server
├── log_sender.py               # Utility to send logs to the server
├── .env                        # Environment variables (e.g., Google Chat API URL)
├── Drain3/
│   └── drain3.py               # Wrapper for the Drain3 log parser
├── LLM/
│   └── llm.py                  # LLM integration for root cause analysis
├── ML/
│   └── rrcf.py                 # RRCF anomaly detection model and multiprocessing logic
├── google_chat_api/
│   └── google_chat_api.py      # Google Chat API integration
└── README.md                   # This documentation
```
# Jakub_log_AI