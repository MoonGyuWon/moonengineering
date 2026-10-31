def render(items) -> str:
    if not items:
        return "(할 일 없음)"
    return "\n".join(
        f"[{'x' if it['done'] else ' '}] {it['id']} {it['title']}" for it in items
    )
