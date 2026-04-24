class ParseFileError(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code
        super().__init__(f"[Error {code}] {message}")

class ExecuteFileError(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code
        super().__init__(f"[Error {code}] {message}")


class LemmaNotFindError(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code
        super().__init__(f"[Error {code}] {message}")


class UnknownExecError(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code
        super().__init__(f"[Error {code}] {message}")
