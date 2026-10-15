"""Failures that must never become usable model predictions."""
class ModelUnavailable(RuntimeError):
    pass


class InvalidModelOutput(RuntimeError):
    pass
