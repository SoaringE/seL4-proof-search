import requests

generate_url = "http://localhost:8192/generate_batch"
prob_url = "http://localhost:8192/compute_logprob"

data = {
    "items": [
        # "proof (prove)\ngoal (1 subgoal):\n 1. \\<lbrace>st_tcb_at runnable t\\<rbrace> delete_caller_cap t' \\<lbrace>\\<lambda>rv. st_tcb_at runnable t\\<rbrace>",
        # "proof (prove)\ngoal (1 subgoal):\n 1. \\<And>w. take_bit LENGTH('a) (take_bit LENGTH('a) (take_bit LENGTH('a) w)) = take_bit LENGTH('a) w",
        # "proof (prove)\ngoal (1 subgoal):\n 1. assumptions True",
        # "proof (prove)\ngoal (1 subgoal):\n 1. \\<lbrakk>is_aligned p' 2; p = p' && ~~ mask ptBits; pte_at' ((p' && ~~ mask ptBits) + (p' && mask ptBits)) s\\<rbrakk> \\<Longrightarrow> pte_at' p' s",
        # "proof (prove)\ngoal (1 subgoal):\n 1. NOT (min x y) = max (NOT x) (NOT y)"
        # "proof (prove)\ngoal (1 subgoal):\n 1. \\<lbrace>valid_objs and valid_cap c and valid_cap c' and tcb_cap_valid c b and tcb_cap_valid c' a\\<rbrace> do y <- set_cap c' a;\ny <- set_cap c b;\nslot1_p <- gets (\\<lambda>s. cdt s a);\nslot2_p <- gets (\\<lambda>s. cdt s b);\ncdt <- gets cdt;\ny <- set_cdt ((\\<lambda>n. if cdt n = Some a then Some b else if cdt n = Some b then Some a else cdt n)(a := if cdt b = Some a then Some b else if cdt b = Some b then Some a else cdt b, b := if cdt a = Some a then Some b else if cdt a = Some b then Some a else cdt a));\ny <- do_extended_op (cap_swap_ext a b slot1_p slot2_p);\nis_original <- gets is_original_cap;\ny <- set_original a (is_original b);\nset_original b (is_original a)\nod \\<lbrace>\\<lambda>rv. valid_objs\\<rbrace>",
        # "proof (prove)\ngoal (1 subgoal):\n 1. if_live_then_nonz_cap s'",
        "proof (prove)\nusing this:\nif_live_then_nonz_cap s\n\ngoal (1 subgoal):\n 1. if_live_then_nonz_cap s'",
    ],
    "sampling_params": {
        "temperature": 1.0,
        "max_tokens": 128,
        "top_p": 0.95,
        "n": 128,
        "logprobs": 1,
        "prompt_logprobs": 1,
    },
    "use_tqdm": True,
}

data["items"] = data["items"]

select_index = 1


response = requests.post(generate_url, json=data, timeout=600)

if response.status_code == 200:
    for i, out in enumerate(response.json()["outputs"]):
        # if i == select_index:
        for j, completion in enumerate(out, start=1):
            print(f"[Example {j}] {completion}")
else:
    print("Request failed: ", response.status_code, response.text)
    


# data = {
#     "state": "proof (prove)\ngoal (1 subgoal):\n 1. \\<lbrace>valid_objs and valid_cap c and valid_cap c' and tcb_cap_valid c b and tcb_cap_valid c' a\\<rbrace> do y <- set_cap c' a;\ny <- set_cap c b;\nslot1_p <- gets (\\<lambda>s. cdt s a);\nslot2_p <- gets (\\<lambda>s. cdt s b);\ncdt <- gets cdt;\ny <- set_cdt ((\\<lambda>n. if cdt n = Some a then Some b else if cdt n = Some b then Some a else cdt n)(a := if cdt b = Some a then Some b else if cdt b = Some b then Some a else cdt b, b := if cdt a = Some a then Some b else if cdt a = Some b then Some a else cdt a));\ny <- do_extended_op (cap_swap_ext a b slot1_p slot2_p);\nis_original <- gets is_original_cap;\ny <- set_original a (is_original b);\nset_original b (is_original a)\nod \\<lbrace>\\<lambda>rv. valid_objs\\<rbrace>",
#     # "state": "proof (prove)\ngoal (1 subgoal):\n 1. \\<lbrace>valid_objs\\<rbrace> doE p <- lookup_slot_for_thread t c;\nliftE (get_cap (fst p))\nodE \\<lbrace>\\<lambda>rv s. \\<exists>cref msk. cte_wp_at (\\<lambda>cap. rv = mask_cap msk cap) cref s\\<rbrace>, -",
#     "possible_steps": [
#         # possible_step[0] for possible_step in response.json()["outputs"][select_index]
#     ],
#     "limit": 128,
#     "sampling_params": {
#         "temperature": 0.0,
#         "max_tokens": 2048,
#         "top_p": 0.95,
#         "n": 1,
#         "logprobs": 1,
#         "prompt_logprobs": 0,
#     },
#     "use_tqdm": True,
# }
# data["possible_steps"].append("apply (frule opt_cap_dom_cdl_objects)")

# data["possible_steps"].append("apply (wp get_cap_gets)")
# data["possible_steps"].append("apply wp")
# data["possible_steps"].append("good morning")
# print("possible: ", data["possible_steps"])

# response = requests.post(prob_url, json=data, timeout=600)

# if response.status_code == 200:
#     for i, out in enumerate(response.json()["outputs"]):
#         print(f"[Suggestion {i + 1}] {out}")
# else:
#     print("Request failed: ", response.status_code, response.text)
