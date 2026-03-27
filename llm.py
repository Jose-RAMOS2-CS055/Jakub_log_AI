import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class llm:
    def __init__(self):
        """
        Initializes the LLM using standard PyTorch and Transformers.
        Optimized for a high-RAM CPU environment, bypassing GPU requirements.
        """
        model_id = "Qwen/Qwen2.5-1.5B-Instruct"

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # Load the model directly to the CPU. 
        # We use bfloat16 to make the math slightly faster for Xeon's AVX-512 instructions.
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            device_map="cpu",          # Force the model to load strictly into system RAM
            torch_dtype=torch.bfloat16, # A CPU-friendly data type that saves space and speeds up math
            trust_remote_code=False
        )
        
    def generate_message_return(self, input_text, k=200):
        """
        Same as generate_message but returns instead of yielding.
        """

        messages = [{"role": "user", "content": input_text}]

        text_prompt = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )

        # Send the tokenized input directly to the CPU
        model_inputs = self.tokenizer(text_prompt, return_tensors="pt").to("cpu")
        
        # --- THE BIG CPU TRICK ---
        # Wrapping the generation in torch.no_grad() tells PyTorch we aren't training the AI.
        # This stops it from calculating gradients, saving a massive amount of memory and speeding up the CPU.
        with torch.no_grad():
            output_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=k,
                pad_token_id=self.tokenizer.eos_token_id # Prevents infinite generation warnings
            )
        
        # Decode the generated token IDs, skipping the prompt part.
        return self.tokenizer.decode(output_ids[0][model_inputs["input_ids"].shape[1]:], skip_special_tokens=True)
