import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from openai import AsyncOpenAI
from loguru import logger

from backend.core.config import get_settings
from backend.core.websocket_manager import ws_manager
from backend.db.models import AgentStep

import ast

settings = get_settings()

def robust_json_loads(s: str) -> dict:
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass

    try:
        val = ast.literal_eval(s)
        if isinstance(val, dict):
            return val
    except Exception:
        pass

    try:
        cleaned = s.replace("True", "true").replace("False", "false").replace("None", "null")
        return json.loads(cleaned)
    except Exception:
        pass
        
    try:
        pythonified = s.replace("true", "True").replace("false", "False").replace("null", "None")
        val = ast.literal_eval(pythonified)
        if isinstance(val, dict):
            return val
    except Exception:
        pass

    raise ValueError(f"Could not parse JSON. Snippet: {s[:200]}")


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, func: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class BaseAgent(ABC):
    name: str = "base"
    system_prompt: str = ""

    def __init__(self, db_session=None, session_id: str = None):
        self.db = db_session
        self.session_id = session_id
        self.client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            timeout=300.0,
        )
        self._tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        self._tools[tool.name] = tool

    async def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"[{self.name}] Starting: {task[:60]}...")
        messages = self._build_messages(task, context)
        max_iterations = 12

        for i in range(max_iterations):
            response = await self._call_qwen(messages)
            message = response.choices[0].message

            if message.content:
                await self._log("thought", message.content)

            if message.tool_calls:
                # Sanitize tool call arguments before adding to history.
                # The API requires arguments to be valid JSON strings.
                # If the LLM produces malformed JSON (e.g. embedding raw
                # invalid payloads), we replace with a cleaned version.
                sanitized_tool_calls = []
                for tc in message.tool_calls:
                    try:
                        # Validate the arguments are parseable JSON
                        parsed = robust_json_loads(tc.function.arguments)
                        clean_args = json.dumps(parsed)
                    except Exception:
                        # Replace unparseable arguments with an error placeholder
                        # so the conversation history stays valid
                        logger.warning(
                            f"[{self.name}] Sanitizing malformed tool args for "
                            f"{tc.function.name}: {tc.function.arguments[:120]}"
                        )
                        clean_args = json.dumps({
                            "error": "malformed_arguments",
                            "raw_snippet": tc.function.arguments[:200],
                        })
                    sanitized_tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": clean_args,
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": sanitized_tool_calls,
                })

                for tc in message.tool_calls:
                    try:
                        args = robust_json_loads(tc.function.arguments)
                        result = await self._execute_tool(tc.function.name, args)
                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to parse/execute tool {tc.function.name}: {e}")
                        result = {"error": f"Failed to parse tool arguments or execute tool: {e}"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
                continue

            # No tool calls = conclusion
            conclusion = self._parse_conclusion(message.content)
            await self._log("conclusion", message.content)
            logger.info(f"[{self.name}] Done in {i+1} iterations.")
            return conclusion

        return {"status": "max_iterations_reached"}

    async def _call_qwen(self, messages: List[dict]):
        tools = [t.to_schema() for t in self._tools.values()]
        kwargs = {
            "model": settings.qwen_model,
            "messages": messages,
            "max_tokens": 2048,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await self.client.chat.completions.create(**kwargs)

    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        await self._log("tool_call", f"Calling: {tool_name}", tool_name=tool_name, tool_input=arguments)
        tool = self._tools.get(tool_name)
        if not tool:
            result = {"error": f"Unknown tool: {tool_name}"}
        else:
            try:
                result = await tool.func(**arguments)
            except Exception as e:
                result = {"error": str(e)}
                logger.error(f"[{self.name}] Tool {tool_name} failed: {e}")
        await self._log("observation", f"Result: {str(result)[:300]}", tool_name=tool_name, tool_output=result)
        return result

    async def _log(self, step_type: str, content: str,
                   tool_name: str = None, tool_input: dict = None, tool_output=None):
        # Stream to frontend
        await ws_manager.emit_agent_step(
            session_id=self.session_id or "system",
            agent=self.name,
            step_type=step_type,
            content=content,
            tool_name=tool_name,
            tool_output=tool_output,
        )
        # Persist to DB
        if self.db and self.session_id:
            step = AgentStep(
                id=str(uuid.uuid4()),
                session_id=self.session_id,
                agent=self.name,
                step_type=step_type,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output if isinstance(tool_output, (dict, list)) else None,
            )
            self.db.add(step)
            await self.db.flush()

    def _build_messages(self, task: str, context: dict = None) -> List[dict]:
        system = self.system_prompt
        if context:
            system += f"\n\nContext:\n{json.dumps(context, indent=2)}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

    def _parse_conclusion(self, content: str) -> dict:
        if not content:
            return {"summary": "No output."}
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return robust_json_loads(content[start:end])
        except Exception:
            pass
        return {"summary": content}

    @abstractmethod
    async def handle(self, *args, **kwargs) -> dict:
        pass
