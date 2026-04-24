timestamp=$(date +%Y%m%d_%H%M%S)
log_dir="logs/${timestamp}"
mkdir -p $log_dir

echo "Logging to $log_dir"

export CUDA_VISIBLE_DEVICES=4,5 && export PYTHONPATH=. && export VLLM_LOGGING_LEVEL=ERROR
python -u eval/tree_search_eval.py \
    --test \
    --test_path datasets/small_test.json \
    --server_num 9 \
    --save_path output/tree_search_eval/small_test.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080 \
    --log_dir $log_dir \
    # --nitpick \
    # --crafted_steps \
    | tee -a $log_dir/output.txt
