from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

class drain3:
    def __init__(self):
        # Setup Drain3 (Parser)
        config = TemplateMinerConfig()
        config.load("") # Loads default configurations
        self.template_miner = TemplateMiner(config=config)
        
    def refactor_logs(self, log_line):
        result = self.template_miner.add_log_message(log_line.strip())
        event_id = result["cluster_id"]
        return result,event_id