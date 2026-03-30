import socket
import time
import re

# ==========================================
# CONFIGURATION
# ==========================================
HOST = '127.0.0.1'
PORT = 1010
FILE_PATH = r'examples\REN-SWEET400-a8n_260120.log' 
WARM_UP = r'examples\REN-SWEET400-a8n.log'
DELAY = 0.01                  
LINES_TO_SEND = 1000

LOG_LINE_START_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}')

def stream_logs_from_file():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
            print(f"[*] Connected to {HOST}:{PORT}")

            # --- Phase 1: Warm-up ---
            print(f"[*] Phase 1: Warming up with {LINES_TO_SEND} lines from '{WARM_UP}'...")
            try:
                with open(WARM_UP, 'r', encoding='utf-8') as file:
                    log_buffer = ""
                    for i, line in enumerate(file, 1):
                        if i > LINES_TO_SEND:
                            break
                        if LOG_LINE_START_REGEX.match(line) and log_buffer:
                            s.sendall((log_buffer + '\n').encode('utf-8'))
                            log_buffer = ""
                            if DELAY > 0:
                                time.sleep(DELAY)

                        if log_buffer == "":
                            log_buffer = line.rstrip()
                        else:
                            log_buffer += " | " + line.rstrip()

                        percentage = (i / LINES_TO_SEND) * 100
                        print(f"[*] Sending line {i}/{LINES_TO_SEND} ({percentage:.2f}%)", end='\r')

                    if log_buffer:
                        s.sendall((log_buffer + '\n').encode('utf-8'))
                print(f"\n[*] Warm-up complete.")
            except FileNotFoundError:
                print(f"\n[!] Error: Could not find the warm-up file '{WARM_UP}'.")
                return # Exit if warm-up file is not found

            # --- Phase 2: Main Log Streaming ---
            print(f"[*] Phase 2: Streaming all lines from '{FILE_PATH}'...")
            try:
                with open(FILE_PATH, 'r', encoding='utf-8') as f:
                    total_lines = sum(1 for _ in f)
                
                with open(FILE_PATH, 'r', encoding='utf-8') as file:
                    log_buffer = ""
                    for i, line in enumerate(file, 1):
                        if LOG_LINE_START_REGEX.match(line) and log_buffer:
                            s.sendall((log_buffer + '\n').encode('utf-8'))
                            log_buffer = ""
                            if DELAY > 0:
                                time.sleep(DELAY)

                        if log_buffer == "":
                            log_buffer = line.rstrip()
                        else:
                            log_buffer += " | " + line.rstrip()

                        percentage = (i / total_lines) * 100
                        print(f"[*] Sending line {i}/{total_lines} ({percentage:.2f}%)", end='\r')

                    if log_buffer:
                        s.sendall((log_buffer + '\n').encode('utf-8'))
                print(f"\n[*] Finished sending all {total_lines} lines from '{FILE_PATH}'.")
            except FileNotFoundError:
                print(f"\n[!] Error: Could not find the main log file '{FILE_PATH}'.")

        except ConnectionRefusedError:
            print(f"\n[!] Connection refused. Is your anomaly detector running on port {PORT}?")

if __name__ == "__main__":
    stream_logs_from_file()