from ML.rrcf import rrcf_model
from google_chat_api.google_chat_api import google_chat_api
from LLM.llm import llm
from Drain3.drain3 import drain3
from collections import deque
from queue import Queue
import socket
import threading
import sys
import os
import seal
# ==========================================
# SYSTEM CONFIGURATION
# ==========================================
sys.setrecursionlimit(3000) # Increases the limit from the default 1000

HOST = '127.0.0.1'
PORT = 1010
HISTORICAL_FILE = r"examples\REN-SWEET400-a8n.log"
MAX_WARMUP_LINES = 100000

# ==========================================
# LLM ANALYSIS AND GOOGLE CHAT MESSAGE
# ==========================================
def call_llm_for_analysis(log_window):
    """
    Takes a window of logs, sends them to the LLM for analysis, and prints the result.
    Designed to be run in a separate thread to not block the main processing loop.
    """
    log_context = "\n".join(log_window)
    
    try:
        analysis = llm_instance.generate_message_return(log_context)
        full_analysis = f"""================ LLM ANALYSIS ================
{analysis}
============================================
================ LOGS ================
{log_context}"""
        
        google_chat_websocket.send_message(full_analysis)
        
    except Exception as e:
        print(f"\n[!!!] Error during LLM analysis: {e}")

# ==========================================
# LOG PROCESSING
# ==========================================
def process_log_line(log_line):
    # Add the raw log line to our recent history
    recent_logs_deque.append(log_line.strip())
    
    # --- A. Parse the Log ---
    result, event_id = drain_instance.refactor_logs(log_line) 
    
    # --- B. Calculate anomaly score ---
    log_snapshot = ML_instance.calculate_anomaly(log_line, result, event_id, recent_logs_deque)
    
    # --- C. Send anomaly report to LLM ---
    if log_snapshot:
        llm_analysis_queue.put(log_snapshot)

# ==========================================
# MODEL WARM-UP (Limited to 3,000 lines)
# ==========================================
def warm_up():
    print(f"[*] Starting Phase 1: Warming up model with the first {MAX_WARMUP_LINES} lines from {HISTORICAL_FILE}...")
    try:
        with open(HISTORICAL_FILE, 'r', encoding='utf-8') as f:
            line_count = 0
            for line in f:
                if line.strip():
                    process_log_line(line)
                    line_count += 1
            
            # Stop reading once we hit the limit
                if line_count >= MAX_WARMUP_LINES:
                    break
                
        print(f"[*] Warm-up complete! Successfully processed {line_count} lines.")
    except FileNotFoundError:
        print(f"[!] Historical file not found. Skipping warm-up.")

# ==========================================
# PORT LOG HANDLER
# ==========================================
def client_handler(conn, addr):
    """Handles an individual client connection, putting logs into a queue."""
    print(f"\n[*] Connection established from {addr}")
    with conn:
        buffer = ""
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                
                # Handle incoming stream and split by newlines
                buffer += data.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        log_queue.put(line)
            except ConnectionResetError:
                break # Client disconnected abruptly
    print(f"[*] Connection closed from {addr}")

# ==========================================
# THREADS
# ==========================================
def log_processor_worker():
    """Worker thread to process logs from the queue."""
    while True:
        line = log_queue.get() # This will block until a log is available
        if line is None: # Sentinel value received, exiting thread.
            break
        process_log_line(line)
        log_queue.task_done()

def llm_analysis_worker():
    """Worker thread to process LLM analysis requests sequentially from a queue."""
    while True:
        log_window = llm_analysis_queue.get() # This will block until a request is available
        call_llm_for_analysis(log_window)
        llm_analysis_queue.task_done()


# ==========================================
# INITIALIZE DRAIN3, RRCF, LLM & GOOGLE CHAT
# ==========================================
recent_logs_deque = deque(maxlen=10)

seal.main()

print(f"[*] Starting Anomaly Detection Engine...")
print(f"[*] Listening for TCP log streams on port {PORT}...")
print("Loading Drain3...")
drain_instance = drain3()
print("Loading RRCF...")
ML_instance = rrcf_model()
print("Loading LLM model...")
llm_instance = llm()
print("Loading Google Chat API...")
google_chat_websocket = google_chat_api()
warm_up()
print(f"[*] Starting Phase 2: Listening for live TCP streams on port {PORT}...")

# ==========================================
# LIVE STREAMING PHASE
# ==========================================
ML_instance.set_alert(True) # Turn on the alarms!
log_queue = Queue()
llm_analysis_queue = Queue()
try:
    # Start the dedicated log processing thread
    processor_thread = threading.Thread(target=log_processor_worker, daemon=True)
    processor_thread.start()

    # Start the dedicated LLM analysis thread
    llm_worker_thread = threading.Thread(target=llm_analysis_worker, daemon=True)
    llm_worker_thread.start()
    
    # Setup the TCP Socket Server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        s.bind((HOST, PORT))
        s.listen()
        
        # THE FIX: Set a 1-second timeout so s.accept() doesn't trap the thread forever
        s.settimeout(1.0) 
        
        while True:
            try:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=client_handler, args=(conn, addr), daemon=True)
                client_thread.start()
            except socket.timeout:
                continue 

except KeyboardInterrupt:
    print("\n[*] Ctrl+C received. Instantly killing the process...")
    os._exit(0)