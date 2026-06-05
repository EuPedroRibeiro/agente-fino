def reflect(state) -> dict:
    return {"summary": getattr(state, "final_answer", "")[:240]}
