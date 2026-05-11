"""
This file is used to run the FullStepProverAPI as a FastAPI server.
Usage: uvicorn provers.fullstep_prover_api:app --host 0.0.0.0 --port 8192
"""

import os
from vllm import LLM, SamplingParams
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import threading
import time
import torch

from transformers import AutoTokenizer

INSTRUCTION = "Given the following Isabelle proof state, suggest the next proof step."


class FullStepProverAPI:
    """
    Abstract base class for Lean 4 code provers using LLMs.
    """

    def __init__(self, model_path, gpu=1, max_model_len=20480, seed=0, **kwargs):
        self.model_path = model_path
        self.model = LLM(
            model=model_path,
            seed=seed,
            swap_space=8,
            tensor_parallel_size=gpu,
            max_model_len=max_model_len,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    def build_prompt(self, input_text):
        """
        Build the prompt for the model based on the input data and optional example.
        """
        if input_text.strip() == "":
            prompt = f"### Instruction:\n{INSTRUCTION}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{INSTRUCTION}\n\n### Input:\n{input_text}\n\n### Response:\n"
        return prompt

    def postprocess(self, model_input, model_output):
        """
        Postprocess the model output to extract the relevant Lean 4 code.
        """
        outputs = [output.text.strip() for output in model_output.outputs]
        logprobs = [output.cumulative_logprob for output in model_output.outputs]
        results = list(dict(zip(outputs, logprobs)).items())
        return results

    def __call__(
        self,
        data_list: list = [],
        sampling_params: SamplingParams = SamplingParams(
            temperature=1.0, max_tokens=2048, top_p=0.95, n=128, logprobs=1
        ),
        retry=10,
        use_tqdm: bool = True,
    ):
        """
        Generate results for a list of data items, supporting nested prompt lists.
        """
        num_data = len(data_list)
        # 1. Build nested prompts (list of lists)
        model_inputs = [self.build_prompt(data) for data in data_list]

        # print("Example of model prompt: ", model_inputs[0])
        # print("max_model_len: ", self.model.llm_engine.model_config.max_model_len)
        filtered_model_inputs = list(
            filter(
                lambda text: (
                    len(self.tokenizer.encode(text))
                    <= (self.model.llm_engine.model_config.max_model_len // 2)
                ),
                model_inputs,
            )
        )

        for i in range(retry):
            prover_outputs = self.model.generate(
                filtered_model_inputs,
                sampling_params,
                use_tqdm=use_tqdm,
            )
            if len(prover_outputs) == len(filtered_model_inputs):
                break
            else:
                print(f"The {i + 1}-th generation is incomplete, retrying...")
                time.sleep(1)

        total_results = []
        available_results = {}
        for i in range(len(prover_outputs)):
            available_results[prover_outputs[i].prompt] = self.postprocess(
                model_inputs[i], prover_outputs[i]
            )

        total_results = [
            available_results.get(model_input, []) for model_input in model_inputs
        ]

        assert len(total_results) == len(model_inputs)

        return total_results

    def compute_logprob(
        self,
        state,
        possible_steps,
        limit,
        sampling_params: SamplingParams = SamplingParams(
            temperature=0.0,
            max_tokens=2048,
            top_p=0.95,
            logprobs=1,
            n=1,
            prompt_logprobs=0,
        ),
        retry=10,
        use_tqdm: bool = True,
    ):
        prompt = self.build_prompt(state)
        full_texts = [prompt + " " + step + "</s>" for step in possible_steps]

        filtered_full_texts = list(
            filter(
                lambda text: (
                    len(self.tokenizer.encode(text))
                    <= self.model.llm_engine.model_config.max_model_len // 4
                ),
                full_texts,
            )
        )

        for i in range(retry):
            prover_outputs = self.model.generate(
                filtered_full_texts, sampling_params, use_tqdm=use_tqdm
            )
            torch.cuda.empty_cache()
            if len(prover_outputs) == len(filtered_full_texts):
                break
            else:
                print(f"The {i + 1}-th generation is incomplete, retrying...")
                time.sleep(1)

        logprobs = []
        available_logprobs = {}
        for i, output in enumerate(prover_outputs):
            # if full_texts[i] == prover_outputs[i].prompt:
            prefix_len = len(self.tokenizer.encode(prompt))
            all_input_ids = self.tokenizer.encode(full_texts[i])
            logprob = sum(
                output.prompt_logprobs[j][all_input_ids[j]].logprob
                for j in range(prefix_len, len(all_input_ids))
            )
            # for j in range(prefix_len, len(all_input_ids)):
            #     logprob += output.prompt_logprobs[j][all_input_ids[j]].logprob
            available_logprobs[prover_outputs[i].prompt] = logprob
            # else:
            #     logprobs.append(-1000.0)
        logprobs = [
            available_logprobs.get(full_text, -1000.0) for full_text in full_texts
        ]

        assert len(logprobs) == len(full_texts)

        # for t, lp in zip(possible_steps, logprobs):
        #     print(f"Target: {t}, Logprob: {lp}")

        results = list(zip(possible_steps, logprobs))
        results.sort(key=lambda p: p[1], reverse=True)
        return results[:limit]


# 1. Define the request body
class SamplingParamsModel(BaseModel):
    temperature: float = 1.0
    max_tokens: int = 2048
    top_p: float = 0.95
    n: int = 128
    logprobs: int = 1


class InferenceBatchRequest(BaseModel):
    items: List[str]
    sampling_params: SamplingParamsModel
    use_tqdm: bool = False


class LogprobSamplingParamsModel(BaseModel):
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: float = 1.0
    n: int = 1
    logprobs: int = 1
    prompt_logprobs: int = 1


class ComputeLogprobRequest(BaseModel):
    state: str
    possible_steps: List[str]
    limit: int
    sampling_params: LogprobSamplingParamsModel
    use_tqdm: bool = False


# 2. Create FastAPI app
app = FastAPI()
lock = threading.Lock()
# 3. Initialize the FullStepProverAPI instance
# Set SFT_MODEL_PATH to the local path of your fine-tuned proof-step model
# (e.g., mistral-7b_full_sft_proofstep). See README for details.
sft_path = os.environ.get("SFT_MODEL_PATH", "")
assert sft_path, "SFT_MODEL_PATH environment variable is not set"
prover = FullStepProverAPI(sft_path, gpu=2)


# 4. Interface
@app.post("/generate_batch")
def generate(request: InferenceBatchRequest):
    sampling_params = SamplingParams(**request.sampling_params.model_dump())
    with lock:
        outputs = prover(
            data_list=request.items,
            sampling_params=sampling_params,
            use_tqdm=request.use_tqdm,
        )
    return {"outputs": outputs}


@app.post("/compute_logprob")
def compute_logprob(request: ComputeLogprobRequest):
    sampling_params = SamplingParams(**request.sampling_params.model_dump())
    with lock:
        outputs = prover.compute_logprob(
            state=request.state,
            possible_steps=request.possible_steps,
            limit=request.limit,
            sampling_params=sampling_params,
            use_tqdm=request.use_tqdm,
        )
    return {"outputs": outputs}


# request_body = {
#   "items": [],
#   "sampling_params": {
#     "temperature": 1.0,
#     "max_tokens": 2048,
#     "top_p": 0.95,
#     "n": 128,
#     "logprobs": 1
#   },
#   "use_tqdm": True
# }
