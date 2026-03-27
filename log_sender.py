import socket
import time
import re

# ==========================================
# CONFIGURATION
# ==========================================
HOST = '127.0.0.1'
PORT = 1010
FILE_PATH = r'examples\REN-SWEET400-a8n_260120.log' 
DELAY = 0.006                  

LOG_LINE_START_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}')

def stream_logs_from_file():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            with open(FILE_PATH, 'r', encoding='utf-8') as f:
                total_lines = sum(1 for _ in f)

            s.connect((HOST, PORT))
            print(f"[*] Connected to {HOST}:{PORT}")
            print(f"[*] Streaming {total_lines} lines from '{FILE_PATH}'...")
            
            with open(FILE_PATH, 'r', encoding='utf-8') as file:
                log_buffer = ""
                for i, line in enumerate(file, 1):
                    
                    # If we find a new timestamp, and we already have a log in the buffer
                    if LOG_LINE_START_REGEX.match(line) and log_buffer:
                        # 1. Add a single '\n' at the very end of the flattened buffer
                        # 2. Send it to the server as ONE single log event
                        s.sendall((log_buffer + '\n').encode('utf-8'))
                        log_buffer = "" 

                        if DELAY > 0:
                            time.sleep(DELAY)

                    # --- THE FLATTENING FIX ---
                    # If the buffer is empty, it's the start of a log.
                    if log_buffer == "":
                        log_buffer = line.rstrip()
                    # If the buffer has data, this is a traceback line! 
                    # Append it using a separator instead of a newline.
                    else:
                        log_buffer += " | " + line.rstrip()

                    percentage = (i / total_lines) * 100
                    print(f"[*] Sending line {i}/{total_lines} ({percentage:.2f}%)", end='\r')

                # Send the final log entry in the buffer
                if log_buffer:
                    s.sendall((log_buffer + '\n').encode('utf-8'))

            print(f"\n[*] Finished sending all {total_lines} lines in the file.")
            
        except FileNotFoundError:
            print(f"[!] Error: Could not find the file '{FILE_PATH}'.")
        except ConnectionRefusedError:
            print(f"\n[!] Connection refused. Is your anomaly detector running on port {PORT}?")

if __name__ == "__main__":
    stream_logs_from_file()