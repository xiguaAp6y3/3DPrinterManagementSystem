from app.core.errors import AppError


ORDER_TRANSITIONS = {
    "submitted": {"reviewing", "payment_confirmed", "cancelled"},
    "reviewing": {"payment_confirmed", "cancelled"},
    "quoted": {"quote_confirmed", "cancelled"},
    "quote_confirmed": {"payment_confirmed", "cancelled"},
    "payment_confirmed": {"scheduled", "cancelled"},
    "scheduled": {"printing", "cancelled"},
    "printing": {"post_processing", "quality_check", "completed", "cancelled"},
    "post_processing": {"quality_check", "completed", "cancelled"},
    "quality_check": {"completed", "cancelled"},
}

CUSTOM_REQUEST_TRANSITIONS = {
    "submitted": {"reviewing"},
    "reviewing": {"need_more_info", "rejected", "quote_pending"},
    "need_more_info": {"submitted"},
    "quote_pending": {"quoted"},
    "quoted": {"quote_confirmed"},
    "quote_confirmed": {"payment_confirmed"},
    "payment_confirmed": {"scheduled"},
}

PRINT_TASK_TRANSITIONS = {
    "pending": {"scheduled", "cancelled"},
    "scheduled": {"printing", "cancelled"},
    "printing": {"paused", "completed", "failed", "cancelled"},
    "paused": {"printing", "cancelled"},
    "failed": {"pending", "cancelled"},
}


def assert_transition(machine: dict[str, set[str]], current: str, target: str) -> None:
    if current == target:
        return
    if target not in machine.get(current, set()):
        raise AppError(
            "INVALID_STATE_TRANSITION",
            f"非法状态流转：{current} -> {target}",
            status_code=409,
            details={"current": current, "target": target},
        )
