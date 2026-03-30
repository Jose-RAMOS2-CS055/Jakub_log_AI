import rrcf
import numpy as np
from collections import deque
import multiprocessing as mp
import sys
import time

sys.setrecursionlimit(3000) 

# ==========================================
# CONFIGURATION
# ==========================================
SHINGLE_SIZE = 4       
TREE_SIZE = 10000      # Bumped to 50,000 to remember weekly patterns
NUM_TREES = 75         
THRESHOLD = 300         
CORES_TO_USE = 18       # Number of background CPU cores to use
ALERT_LOG_FILE = 'anomaly_alerts_' # File to save alerts

# ==========================================
# 1. THE MULTIPROCESSING WORKER
# ==========================================
# MUST be outside the class so it can be sent to other CPU cores
def rrcf_worker(log_queue, result_queue, num_trees, tree_size):
    local_forest = [rrcf.RCTree() for _ in range(num_trees)]
    point_index = 0
    
    while True:
        point = log_queue.get()
        if point is None: # Poison pill to shut down
            break
            
        local_codisp = 0
        for tree in local_forest:
            if len(tree.leaves) > tree_size:
                tree.forget_point(point_index - tree_size)
                
            tree.insert_point(point, index=point_index)
            local_codisp += tree.codisp(point_index)
            
        result_queue.put(local_codisp / num_trees)
        point_index += 1

# ==========================================
# 2. YOUR REFACTORED CLASS
# ==========================================
class rrcf_model:
    def __init__(self, max_warmup_lines):
        self.trees_per_core = NUM_TREES // CORES_TO_USE
        self.max_warmup_lines = max_warmup_lines
        
        # IPC Queues
        self.log_queues = [mp.Queue() for _ in range(CORES_TO_USE)]
        self.result_queues = [mp.Queue() for _ in range(CORES_TO_USE)]
        
        # Spin up background workers
        self.workers = []
        for i in range(CORES_TO_USE):
            p = mp.Process(
                target=rrcf_worker, 
                args=(self.log_queues[i], self.result_queues[i], self.trees_per_core, TREE_SIZE)
            )
            p.start()
            self.workers.append(p)
            
        self.shingle_deque = {}
        self.warmup_status = {}
        self.log_path = {}
        self.known_shingles = [] # To track order for printing
        
    def create_new_shingle(self, id):
        self.shingle_deque[id] = deque(maxlen=SHINGLE_SIZE)
        self.log_path[id] = ALERT_LOG_FILE + str(id).replace(":", "_") + '.log'
        self.warmup_status[id] = {'lines_processed': 0, 'warmup_complete': False}
        
    def calculate_anomaly(self, log_line, result, event_id, recent_logs_deque, shingle_id):
        # --- Per-Client Warm-up Logic ---
        status = self.warmup_status[shingle_id]
        status['lines_processed'] += 1
        if not status['warmup_complete']:
            if status['lines_processed'] >= self.max_warmup_lines:
                status['warmup_complete'] = True
                print(f"\n[*] Warm-up complete for {shingle_id}. Live anomaly detection is now active for this client.")

        # --- Consolidated Status Display ---
        if shingle_id not in self.known_shingles:
            self.known_shingles.append(shingle_id)

        # Update the display periodically to avoid performance bottlenecks
        if status['lines_processed'] % 10 == 0:
            # ANSI escape code to clear screen and move cursor to top-left
            print("\033[H\033[J", end="") 
            print("--- Live Client Status ---")
            for s_id in self.known_shingles:
                s_status = self.warmup_status.get(s_id, {})
                s_lines = s_status.get('lines_processed', 0)
                print(f"[*] Client {s_id}: {s_lines} lines processed")
        self.shingle_deque[shingle_id].append(event_id)
        if len(self.shingle_deque[shingle_id]) < SHINGLE_SIZE:
            return None 
        
        # --- THE JITTER FIX ---
        point = np.array(self.shingle_deque[shingle_id], dtype=float)
        point = point + np.random.uniform(low=-1e-5, high=1e-5, size=point.shape)

        # Dispatch to all cores
        for q in self.log_queues:
            q.put(point)

        # Collect scores from all cores
        total_score = 0
        for q in self.result_queues:
            total_score += q.get()
            
        avg_codisp = total_score / CORES_TO_USE
        
        # --- Alerting ---
        if status['warmup_complete'] and avg_codisp > THRESHOLD:
            if "INFO" not in log_line:
                # print(f"\n[!!!] ANOMALY DETECTED [!!!]")
                # print(f"Score: {avg_codisp:.2f}")
                # print(f"Log: {log_line.strip()}")
                # print(f"Pattern Template: {result['template_mined']}")

                # --- Write alert to a text file ---
                try:
                    with open(self.log_path[shingle_id], 'a', encoding='utf-8') as f:
                        f.write("="*50 + "\n")
                        f.write(f"Timestamp: {time.ctime()}\n")
                        f.write(f"Score: {avg_codisp:.2f}\n")
                        f.write(f"Log: {log_line.strip()}\n")
                        f.write(f"Pattern Template: {result['template_mined']}\n\n")
                except Exception as e:
                    print(f"\n[!] Error writing alert to file: {e}")

                log_snapshot = list(recent_logs_deque)
                return log_snapshot
                
        return None
        
    def shutdown(self):
        """Cleanly kill the background CPU cores"""
        for q in self.log_queues:
            q.put(None)
        for p in self.workers:
            p.join()