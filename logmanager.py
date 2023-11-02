import os
import json

class LogManager:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def save_log(self, branch_name, log):
        log_file = os.path.join(self.log_dir, f"{branch_name}.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log) + '\n')

    def load_log(self, branch_name):
        log_file = os.path.join(self.log_dir, f"{branch_name}.jsonl")
        if not os.path.exists(log_file):
            return []
        with open(log_file, 'r') as f:
            return [json.loads(line) for line in f]

    def find_common_ancestor(self, branch1, branch2):
        # TODO: Implement this method
        pass

    def handle_edit(self, branch_name, edited_log):
        # TODO: Implement this method
        pass
