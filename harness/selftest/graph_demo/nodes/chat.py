"""LLM 노드 — 제공자는 프로그램의 llm.py (없으면 mocks/llm.json). 노드는 ctx.llm 만 안다."""


def run(state, ctx):
    return {"result": ctx.llm(f"한 문장으로 답하라. 질문: {state['q']}").strip()}
