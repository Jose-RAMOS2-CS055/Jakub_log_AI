import rrcf
import numpy as np
from collections import deque
from queue import Queue
import sys
sys.setrecursionlimit(3000) # Increases the limit from the default 1000

SHINGLE_SIZE = 4       # How many logs to look at in a sequence
TREE_SIZE = 3000        # How many points the RRCF remembers (sliding window for drift)
NUM_TREES = 75         # Number of trees in the forest (utilizes your CPU cores)
THRESHOLD = 95         # Anomaly score threshold (tune this over time)

class rrcf_model:
    def __init__(self):
        self.forest = []
        for _ in range(NUM_TREES):
            tree = rrcf.RCTree()
            self.forest.append(tree)
            
        self.shingle_deque = deque(maxlen=SHINGLE_SIZE)
        self.point_index = 0
        self.total_lines_processed = 0
        self.llm_analysis_queue = Queue()
        self.alert = False
        
    def set_alert(self, alert):
        self.alert = alert
        
    def calculate_anomaly(self, log_line, result, event_id, recent_logs_deque):
        self.shingle_deque.append(event_id)
        if len(self.shingle_deque) < SHINGLE_SIZE:
            return # Wait until we have enough logs to form a pattern
        
        # Convert sequence to a numeric point for the RRCF model
        point = np.array(self.shingle_deque, dtype=float)

        # --- Score & Update the RRCF Trees ---
        avg_codisp = 0
        for tree in self.forest:
            # 1. If the tree is full, "forget" the oldest point to handle concept drift over months
            if len(tree.leaves) > TREE_SIZE:
                oldest_index = self.point_index - TREE_SIZE
                tree.forget_point(oldest_index)
                
            # 2. Insert the new log sequence into the tree
            tree.insert_point(point, index=self.point_index)
            
            # 3. Calculate the "Collusive Displacement" (Anomaly Score)
            avg_codisp += tree.codisp(self.point_index)
            
        avg_codisp /= NUM_TREES
        self.point_index += 1

        # Increment and display the total number of lines processed
        self.total_lines_processed += 1
        print(f"[*] Lines Processed: {self.total_lines_processed}", end='\r')
        
        # --- Alerting ---
        # Only alert if the score is high AND the log is NOT an INFO log
        if self.alert and avg_codisp > THRESHOLD:
            if "INFO" not in log_line:
                print(f"\n[!!!] ANOMALY DETECTED [!!!]")
                print(f"Score: {avg_codisp:.2f}")
                print(f"Log: {log_line.strip()}")
                print(f"Pattern Template: {result['template_mined']}")

                # Create a snapshot of the current log window to pass to the thread
                log_snapshot = list(recent_logs_deque)
                return log_snapshot
        return None
