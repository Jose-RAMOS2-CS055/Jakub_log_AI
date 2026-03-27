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
# ==========================================
# SYSTEM CONFIGURATION
# ==========================================
sys.setrecursionlimit(3000) # Increases the limit from the default 1000

HOST = '127.0.0.1'
PORT = 1010
HISTORICAL_FILE = r"examples\REN-SWEET400-a8n.log"
MAX_WARMUP_LINES = 9000

def call_llm_for_analysis(log_window):
    log_context = "\n".join(log_window)
    try:
        analysis = llm_instance.generate_message_return(log_context)
        full_analysis = f"================ LLM ANALYSIS ================\n{analysis}\n============================================\n================ LOGS ================\n{log_context}"
        google_chat_websocket.send_message(full_analysis)
    except Exception as e:
        print(f"\n[!!!] Error during LLM analysis: {e}")

def process_log_line(log_line):
    recent_logs_deque.append(log_line.strip())
    result, event_id = drain_instance.refactor_logs(log_line) 
    log_snapshot = ML_instance.calculate_anomaly(log_line, result, event_id, recent_logs_deque)
    if log_snapshot:
        llm_analysis_queue.put(log_snapshot)

def warm_up():
    print(f"[*] Starting Phase 1: Warming up model with the first {MAX_WARMUP_LINES} lines from {HISTORICAL_FILE}...")
    try:
        with open(HISTORICAL_FILE, 'r', encoding='utf-8') as f:
            line_count = 0
            for line in f:
                if line.strip():
                    process_log_line(line)
                    line_count += 1
                if line_count >= MAX_WARMUP_LINES:
                    break
        print(f"\n[*] Warm-up complete! Successfully processed {line_count} lines.")
    except FileNotFoundError:
        print(f"\n[!] Historical file not found. Skipping warm-up.")

def client_handler(conn, addr):
    print(f"\n[*] Connection established from {addr}")
    with conn:
        buffer = ""
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        log_queue.put(line)
            except ConnectionResetError:
                break 
    print(f"[*] Connection closed from {addr}")

def log_processor_worker():
    while True:
        line = log_queue.get() 
        if line is None: 
            break
        process_log_line(line)
        log_queue.task_done()

def llm_analysis_worker():
    while True:
        log_window = llm_analysis_queue.get() 
        call_llm_for_analysis(log_window)
        llm_analysis_queue.task_done()


# ==========================================
# MAIN EXECUTION (WINDOWS MULTIPROCESSING GUARD)
# ==========================================
if __name__ == '__main__':
    # Initialize Queues FIRST so warm_up can use them
    recent_logs_deque = deque(maxlen=10)
    log_queue = Queue()
    llm_analysis_queue = Queue()

    print(f"[*] Starting Anomaly Detection Engine...")
    print("Loading Drain3...")
    drain_instance = drain3()
    print("Loading RRCF...")
    ML_instance = rrcf_model()
    print("Loading LLM model...")
    llm_instance = llm()
    print("Loading Google Chat API...")
    google_chat_websocket = google_chat_api()

    # WARM UP PHASE
    warm_up()
    
    # LIVE STREAMING PHASE
    print(f"[*] Starting Phase 2: Listening for live TCP streams on port {PORT}...")
    ML_instance.set_alert(True) 

    try:
        processor_thread = threading.Thread(target=log_processor_worker, daemon=True)
        processor_thread.start()

        llm_worker_thread = threading.Thread(target=llm_analysis_worker, daemon=True)
        llm_worker_thread.start()
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            s.bind((HOST, PORT))
            s.listen()
            s.settimeout(1.0) 
            
            while True:
                try:
                    conn, addr = s.accept()
                    client_thread = threading.Thread(target=client_handler, args=(conn, addr), daemon=True)
                    client_thread.start()
                except socket.timeout:
                    continue 

    except KeyboardInterrupt:
        print("\n[*] Ctrl+C received. Shutting down multiprocessing cores cleanly...")
        # CRITICAL: Clean up the spawned cores before exiting
        ML_instance.shutdown()
        os._exit(0)