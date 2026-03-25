# ToolResult
# ReactState
# ReactConfig
# ReactOrchestrator

# --------------------------- guideline -------------------------

# from typing import Callable, Any, Optional
# from dataclasses import dataclass

# @dataclass
# class ToolResult:
#     """Result จากการ execute tool"""
#     tool_name: str
#     status: str              # "success" or "error"
#     data: dict              # ข้อมูลจาก tool
#     error: Optional[str] = None

# @dataclass
# class ReactState:
#     """State ที่เปลี่ยนไปใน loop"""
#     market_state: dict
#     tool_results: list[ToolResult]  # accumulated results
#     iteration: int
#     tool_call_count: int
#     react_trace: list[dict]         # เก็บ trace ทุก step

# class ReactOrchestrator:
#     """
#     Main orchestrator สำหรับ ReAct loop
    
#     Design: fully dependency-injected
#     - LLM client ส่งเข้ามา (A)
#     - Prompt builder ส่งเข้ามา (C)
#     - Tool registry ส่งเข้ามา
#     - Config ส่งเข้ามา
#     """
    
#     def __init__(
#         self,
#         llm_client: LLMClient,                    # from A
#         prompt_builder: "PromptBuilder",          # from C
#         tool_registry: dict[str, Callable],
#         config: ReactConfig,
#     ):
#         self.llm = llm_client
#         self.prompt_builder = prompt_builder
#         self.tools = tool_registry
#         self.config = config
    
#     def run(
#         self,
#         market_state: dict,
#         initial_observation: Optional[ToolResult] = None,
#     ) -> dict:
#         """
#         Run เต็มๆ ReAct loop
        
#         Returns:
#             {
#                 "final_decision": {...},
#                 "react_trace": [...],
#                 "iterations_used": int,
#                 "tool_calls_used": int,
#             }
#         """
#         state = ReactState(
#             market_state=market_state,
#             tool_results=[initial_observation] if initial_observation else [],
#             iteration=0,
#             tool_call_count=0,
#             react_trace=[],
#         )
        
#         final_decision = None
        
#         while state.iteration < self.config.max_iterations:
#             state.iteration += 1
            
#             # STEP 1: Thought - LLM analyzes
#             prompt = self.prompt_builder.build_thought(
#                 state.market_state,
#                 state.tool_results,
#                 state.iteration,
#             )
#             response = self.llm.call(prompt)
#             thought = self._parse_response(response)
            
#             state.react_trace.append({
#                 "step": "THOUGHT",
#                 "iteration": state.iteration,
#                 "response": thought,
#             })
            
#             # STEP 2: Action - ตัดสินใจว่าทำอะไร
#             action = thought.get("action")  # "CALL_TOOL" or "FINAL_DECISION"
            
#             if action == "FINAL_DECISION":
#                 final_decision = thought
#                 break
            
#             elif action == "CALL_TOOL":
#                 if state.tool_call_count >= self.config.max_tool_calls:
#                     # Max tool calls reached
#                     final_decision = self._fallback_decision()
#                     break
                
#                 # STEP 3: Observation - Execute tool
#                 tool_name = thought.get("tool_name")
#                 tool_args = thought.get("tool_args", {})
                
#                 observation = self._execute_tool(tool_name, tool_args)
#                 state.tool_results.append(observation)
#                 state.tool_call_count += 1
                
#                 state.react_trace.append({
#                     "step": "TOOL_EXECUTION",
#                     "iteration": state.iteration,
#                     "tool_name": tool_name,
#                     "observation": observation,
#                 })
                
#                 # Loop back to Thought
#                 continue
            
#             else:
#                 # Unknown action
#                 final_decision = self._fallback_decision()
#                 break
        
#         # STEP 4: Build output
#         return {
#             "final_decision": final_decision or self._fallback_decision(),
#             "react_trace": state.react_trace,
#             "iterations_used": state.iteration,
#             "tool_calls_used": state.tool_call_count,
#         }
    
#     def _execute_tool(self, tool_name: str, tool_args: dict) -> ToolResult:
#         """
#         Execute tool จาก registry
        
#         Returns:
#             ToolResult with status, data, error
#         """
#         if tool_name not in self.tools:
#             return ToolResult(
#                 tool_name=tool_name,
#                 status="error",
#                 data={},
#                 error=f"Tool '{tool_name}' not found",
#             )
        
#         try:
#             result = self.tools[tool_name](**tool_args)
#             return ToolResult(
#                 tool_name=tool_name,
#                 status="success",
#                 data=result,
#             )
#         except Exception as e:
#             return ToolResult(
#                 tool_name=tool_name,
#                 status="error",
#                 data={},
#                 error=str(e),
#             )
    
#     def _parse_response(self, raw_response: str) -> dict:
#         """ใช้ extract_json จาก utils"""
#         return extract_json(raw_response)
    
#     def _fallback_decision(self) -> dict:
#         """Return HOLD signal as fallback"""
#         return {
#             "action": "FINAL_DECISION",
#             "signal": "HOLD",
#             "confidence": 0.0,
#         }

# @dataclass
# class ReactConfig:
#     """Config สำหรับ ReAct loop"""
#     max_iterations: int = 10
#     max_tool_calls: int = 5
#     timeout_seconds: Optional[int] = None