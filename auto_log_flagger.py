import socket
from ML.rrcf import rrcf_model
import numpy as np
from collections import deque
import threading
from queue import Queue
import sys
from LLM.llm import llm
from Drain3.drain3 import drain3
import os
sys.setrecursionlimit(3000) # Increases the limit from the default 1000

# ==========================================
# 1. SYSTEM CONFIGURATION
# ==========================================
HOST = '0.0.0.0'       # Listen on all network interfaces
PORT = 1010            # The port you requested
HISTORICAL_FILE = r"examples\REN-SWEET400-a8n.log"
MAX_WARMUP_LINES = 3000

# ==========================================
# 3. THE REAL-TIME LISTENER & PROCESSOR
# ==========================================
def call_llm_for_analysis(log_window):
    """
    Takes a window of logs, sends them to the LLM for analysis, and prints the result.
    Designed to be run in a separate thread to not block the main processing loop.
    """
    print("\n[+] Anomaly confirmed. Sending to LLM for root cause analysis...")
    
    # The deque is passed as a list, convert it to a newline-separated string
    log_context = "\n".join(log_window)
    
    # Call the LLM
    try:
        analysis = llm_instance.generate_message_return(log_context)
        
        # Print the analysis
        print("\n================ LLM ANALYSIS ================")
        print(analysis)
        print("============================================\n")
    except Exception as e:
        print(f"\n[!!!] Error during LLM analysis: {e}")

def process_log_line(log_line):
    # Add the raw log line to our recent history
    recent_logs_deque.append(log_line.strip())
    
    # --- A. Parse the Log ---
    result, event_id = drain_instance.refactor_logs(log_line) 
    
    # --- B. Vectorize (Create a Shingle) ---
    # We group the last N events together to catch sequential anomalies
    log_snapshot = ML_instance.calculate_anomaly(log_line, result, event_id, recent_logs_deque)
    
    if log_snapshot:
        llm_analysis_queue.put(log_snapshot)

# ==========================================
# PHASE 1: WARM-UP (Limited to 3,000 lines)
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



# 2. INITIALIZE DRAIN3 & RRCF & LLM
# ==========================================
recent_logs_deque = deque(maxlen=10)

print(f"[*] Starting Anomaly Detection Engine...")
print(f"[*] Listening for TCP log streams on port {PORT}...")
print(f"Now loading the LLM model...")
llm_instance = llm()
drain_instance = drain3()
ML_instance = rrcf_model()
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
                # If no connection happens in 1 second, it throws a timeout.
                # We catch it and 'continue' the loop. 
                # This tiny interruption allows Python to "hear" your Ctrl+C!
                continue 

except KeyboardInterrupt:
    print("\n[*] Ctrl+C received. Instantly killing the process...")
    os._exit(0)