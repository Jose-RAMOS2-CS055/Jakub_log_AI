import socket
import time

# ==========================================
# CONFIGURATION
# ==========================================
HOST = '127.0.0.1'
PORT = 1010
FILE_PATH = r'examples\REN-SWEET400-a8n_260120.log'  # <-- CHANGE THIS TO YOUR .TXT FILE NAME
DELAY = 0.01                  # Seconds to wait between sending each line

def stream_logs_from_file():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Get total line count for progress bar without loading the whole file into memory
            with open(FILE_PATH, 'r', encoding='utf-8') as f:
                total_lines = sum(1 for _ in f)

            s.connect((HOST, PORT))
            print(f"[*] Connected to {HOST}:{PORT}")
            print(f"[*] Streaming {total_lines} logs from '{FILE_PATH}'...")
            
            with open(FILE_PATH, 'r', encoding='utf-8') as file:
                for i, line in enumerate(file, 1):
                    # Clean up the line and ensure it ends with a newline character
                    clean_line = line.strip() + '\n'
                    
                    # Send it over the TCP socket
                    s.sendall(clean_line.encode('utf-8'))
                    
                    # Calculate and print progress
                    percentage = (i / total_lines) * 100
                    print(f"[*] Sending log {i}/{total_lines} ({percentage:.2f}%)", end='\r')

                    # Optional: Pause slightly to simulate real-time log generation.
                    # If you want to blast the whole file instantly, set DELAY = 0
                    if DELAY > 0:
                        time.sleep(DELAY)
                        
            print(f"\n[*] Finished sending all {total_lines} logs in the file.")
            
        except FileNotFoundError:
            print(f"[!] Error: Could not find the file '{FILE_PATH}'. Make sure it's in the same folder.")
        except ConnectionRefusedError:
            # Add a newline to not overwrite the progress bar if it was running
            print(f"\n[!] Connection refused. Is your anomaly detector running on port {PORT}?")

if __name__ == "__main__":
    stream_logs_from_file()