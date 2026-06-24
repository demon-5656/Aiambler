from __future__ import annotations


class AiamblerError(Exception):
    code = "ERR_AIAMBLER"

    def __init__(self, message: str, *, line: int | None = None, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.details = details

    def __str__(self) -> str:
        parts = [self.code]
        if self.line is not None:
            parts.append(f"line: {self.line}")
        parts.append(f"reason: {self.message}")
        for key, value in self.details.items():
            parts.append(f"{key}: {value}")
        return "\n".join(parts)


class ParseError(AiamblerError):
    code = "ERR_PARSE"


class AccessDeniedError(AiamblerError):
    code = "ERR_ACCESS_DENIED"


class UnknownCommandError(AiamblerError):
    code = "ERR_UNKNOWN_COMMAND"


class UnknownFieldError(AiamblerError):
    code = "ERR_UNKNOWN_FIELD"


class RuntimeAiamblerError(AiamblerError):
    code = "ERR_RUNTIME"

