CUDA_VISIBLE_DEVICES=4,5 uvicorn provers.fullstep_prover_api:app \
    --host 0.0.0.0 \
    --port 8080 > logs/server.log 2>&1 