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
MAX_WARMUP_LINES = 1000 # The number of log lines to process before activating anomaly alerts

def call_llm_for_analysis(log_window):
    log_context = "\n".join(log_window)
    try:
        analysis = llm_instance.generate_message_return(log_context)
        full_analysis = f"================ LLM ANALYSIS ================\n{analysis}\n============================================\n================ LOGS ================\n{log_context}"
        google_chat_websocket.send_message(full_analysis)
    except Exception as e:
        print(f"\n[!!!] Error during LLM analysis: {e}")

def process_log_line(log_line, source_id):
    recent_logs_deque.append(log_line.strip())
    result, event_id = drain_instance.refactor_logs(log_line) 
    log_snapshot = ML_instance.calculate_anomaly(log_line, result, event_id, recent_logs_deque, source_id)
    if log_snapshot:
        llm_analysis_queue.put(log_snapshot)

def client_handler(conn, addr):
    client_id = f"{addr[0]}:{addr[1]}" # Generate a unique ID for client connections
    print(f"\n[*] Connection established from {client_id}")
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
                        log_queue.put((line, client_id))
            except ConnectionResetError:
                break 
    print(f"[*] Connection closed from {client_id}")

def log_processor_worker():
    while True:
        item = log_queue.get() 
        if item is None: 
            break
        line, source_id = item
        if source_id not in ML_instance.shingle_deque:
            ML_instance.create_new_shingle(source_id)
        process_log_line(line, source_id)

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
    recent_logs_deque = deque(maxlen=10)
    log_queue = Queue()
    llm_analysis_queue = Queue()
    seal.main()

    print(f"[*] Starting Anomaly Detection Engine...")
    print("Loading Drain3...")
    drain_instance = drain3()
    print("Loading RRCF...")
    ML_instance = rrcf_model(max_warmup_lines=MAX_WARMUP_LINES)
    print("Loading LLM model...")
    llm_instance = llm()
    print("Loading Google Chat API...")
    google_chat_websocket = google_chat_api()

    # The system will now warm up using the first MAX_WARMUP_LINES from the TCP stream.
    print(f"[*] Waiting for connections on port {PORT}...")
    print(f"[*] Model will warm up with the first {MAX_WARMUP_LINES} log lines from each new connection.")

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