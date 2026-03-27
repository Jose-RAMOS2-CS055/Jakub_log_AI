from drain3.template_miner_config import TemplateMinerConfig
from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction

class drain3:
    def __init__(self):
        config = TemplateMinerConfig()
        
        # ==========================================
        # CUSTOM MASKING INSTRUCTIONS (CORRECTED)
        # ==========================================
        config.masking_instructions = [
            # 1. Mask the Date (e.g., 2025-10-14)
            MaskingInstruction(r"\d{4}-\d{2}-\d{2}", "*"),
            
            # 2. Mask the Time with milliseconds (e.g., 11:40:42,108 or 11:40:42.108)
            MaskingInstruction(r"\d{2}:\d{2}:\d{2}[,\.]\d{3}", "*"),
            
            # 3. Mask anything inside parentheses (e.g., (8892547) or (73: PRA1...) )
            MaskingInstruction(r"\([\w\s:-]+\)", "*"),
            
            # 4. Mask any other standalone numbers
            MaskingInstruction(r"\b\d+\b", "*"),
        ]

        # Pass the custom config to the miner
        self.template_miner = TemplateMiner(config=config)
        
    def refactor_logs(self, log_line):
        result = self.template_miner.add_log_message(log_line)
        return result, result["cluster_id"]