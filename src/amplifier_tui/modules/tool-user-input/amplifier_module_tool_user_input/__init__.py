"""Independent Amplifier tool. Hosts provide user.questions; no terminal imports."""

from amplifier_core import ToolResult

__amplifier_module_type__ = "tool"


class UserInputTool:
    name = "request_user_input"
    description = (
        "Ask the user 1–3 questions and wait for explicit answers. Offer up to 6 choices "
        "per question, or omit choices for free text. The user may always write their own "
        "answer. Use only for clarification, never permission to execute tools. "
        "Cancellation or timeout supplies no answer; do not assume a default."
    )
    input_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["questions"],
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "question"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
                        "question": {"type": "string", "minLength": 1, "maxLength": 2000},
                        "options": {
                            "type": "array",
                            "maxItems": 6,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["label"],
                                "properties": {
                                    "label": {"type": "string", "minLength": 1, "maxLength": 100},
                                    "description": {"type": "string", "maxLength": 1000},
                                },
                            },
                        },
                    },
                },
            }
        },
    }

    def __init__(self, coordinator, config):
        self.coordinator, self.config = coordinator, config

    async def execute(self, input):
        capability = self.coordinator.get_capability("user.questions")
        if not callable(capability):
            return ToolResult(
                success=False, error={"message": "This host has no interactive question capability"}
            )
        try:
            result = await capability(
                input.get("questions"),
                session_id=self.coordinator.session_id,
                timeout=self.config.get("timeout", 600),
            )
        except (TypeError, ValueError) as exc:
            return ToolResult(success=False, error={"message": str(exc)})
        return ToolResult(
            success=result["status"] == "answered",
            output=result,
            error=None
            if result["status"] == "answered"
            else {"message": f"User questions: {result['status']}; no answer supplied"},
        )


async def mount(coordinator, config):
    if "request_user_input" in (coordinator.get("tools") or {}):
        raise RuntimeError("request_user_input is already mounted; refusing to replace its policy")
    await coordinator.mount(
        "tools", UserInputTool(coordinator, config or {}), name="request_user_input"
    )
