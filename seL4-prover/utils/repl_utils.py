def parse_str_output(raw_result: str):
    # print(step_result)
    # print("*****************************")
    success, message = raw_result.split("<\\SEP>")
    if success == "True":
        return True, message
    else:
        return False, message

def parse_hammer_facts_output(raw_output: str):
    # print(raw_output[:100])
    result_split = raw_output.split("<\\SEP>")
    success = result_split[0]
    if success == "False":
        num = 0
        result_lst = []
        error_message = result_lst[1]
        return (False, num, result_lst, error_message)
    else:
        num = int(result_split[1])
        # print("further", result_split[2][:100])
        result_lst = [result.split("<\\INNER_SEP>") for result in result_split[3:]]
        result_lst = [{"theory": result[0], "fact": result[1], "fact_definition": result[2].strip()} for result in result_lst]
        error_message = ""
        return (True, num, result_lst, error_message)
    
def parse_thms_in_parent_output(raw_output: str):
    result_split = raw_output.split("<\\SEP>")
    success = result_split[0]
    if success == "False":
        num = 0
        result_lst = []
        error_message = result_lst[1]
        return (False, num, result_lst, error_message)
    else:
        result_lst = result_split[1:]
        num = len(result_lst)
        error_message = ""
        return (True, num, result_lst, error_message)
    
def parse_dependent_thms_output(raw_output: str):
    result_split = raw_output.split("<\\SEP>")
    success = result_split[0]
    if success == "False":
        num = 0
        result_lst = []
        error_message = result_split[1]
        return (False, num, result_lst, error_message)
    else:
        result_lst = result_split[1:]
        result_lst = [result.split("<\\INNER_SEP>") for result in result_lst]
        result_lst = [{"theory": result[0], "fact": result[1]} for result in result_lst]
        num = len(result_lst)
        error_message = ""
        return (True, num, result_lst, error_message)
    
def parse_hammer_prove_output(raw_output: str):
    # print(raw_output)
    result_split = raw_output.split("<\\SEP>")
    success = result_split[0]
    if success == "False":
        num = 0
        result_lst = []
        error_message = result_split[1]
        return (False, num, result_lst, error_message)
    else:
        result_lst = result_split[1:]
        num = len(result_lst)
        error_message = ""
        return (True, num, result_lst, error_message)
