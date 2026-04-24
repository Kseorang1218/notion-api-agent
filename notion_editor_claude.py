"""
Notion 연구방법 페이지 편집기 (Claude + Tool Use 버전)

Claude AI 모델이 Notion API를 직접 호출하여 페이지 블록을 읽고/추가/수정/삭제하는
Tool-Use 기반 에이전트입니다.

사용자가 자연어로 지시하면 Claude가 적절한 Notion API 도구를 선택하여
페이지 편집 작업을 자동 수행합니다.

사전 준비:
  1. .env 파일에 NOTION_TOKEN, PAGE_ID, AICHAT_KEY 설정
  2. pip install requests python-dotenv openai 로 의존성 설치
"""
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

# ========== 환경 변수 및 설정 ==========
# .env 파일에서 환경 변수를 불러옴 (토큰, 키 등 민감 정보 분리 관리)
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")   # Notion 통합(Integration) 시크릿 토큰
PAGE_ID      = os.getenv("PAGE_ID")        # 편집 대상 Notion 페이지 ID
AICHAT_KEY   = os.getenv("AICHAT_KEY")     # LLM API 인증 키 (FactChat 게이트웨이용)


# 사용할 LLM 모델명 (Claude Opus 4-7)
MODEL = "claude-opus-4-7"

# Notion API 요청 시 공통으로 사용하는 HTTP 헤더
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",   # 인증 토큰
    "Notion-Version": "2022-06-28",               # Notion API 버전
    "Content-Type": "application/json",            # JSON 통신
}

# OpenAI 호환 클라이언트 생성 (FactChat 게이트웨이를 통해 Claude 모델 호출)
llm = OpenAI(api_key=AICHAT_KEY, base_url="https://factchat-cloud.mindlogic.ai/v1/gateway")


# ========== Notion API 래퍼 함수들 ==========
# 아래 함수들은 Notion REST API를 직접 호출하여 블록을 CRUD 합니다.

def _rt(text):
    """Notion rich_text 형식으로 변환하는 헬퍼.
    일반 문자열을 Notion API가 요구하는 rich_text 배열 형태로 감싸줍니다."""
    return [{"type": "text", "text": {"content": text}}]

def _block(kind, text):
    """Notion 블록 객체 생성 헬퍼.
    kind: 블록 유형 (paragraph, heading_1 등)
    text: 블록에 들어갈 텍스트 내용"""
    return {"object": "block", "type": kind, kind: {"rich_text": _rt(text)}}


def notion_get_page_blocks(page_id: str):
    """페이지 내 전체 블록 목록 조회.
    Notion API는 한 번에 최대 100개 블록만 반환하므로,
    커서 기반 페이지네이션으로 모든 블록을 수집합니다.
    반환값: [{"id": 블록ID, "type": 블록유형, "text": 텍스트내용}, ...]"""
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=NOTION_HEADERS).json()
        blocks.extend(r.get("results", []))
        if not r.get("has_more"): break
        cursor = r.get("next_cursor")

    # 전체 블록 데이터에서 id, type, text만 추출하여 간소화
    simplified = []
    for b in blocks:
        t = b["type"]
        text = ""
        if t in b and "rich_text" in b[t]:
            text = "".join(x.get("plain_text", "") for x in b[t]["rich_text"])
        simplified.append({"id": b["id"], "type": t, "text": text})
    return simplified


def notion_append_blocks(page_id: str, items: list):
    """페이지 맨 끝에 새 블록들을 추가.
    items: [{"type": "paragraph", "text": "내용"}, ...] 형태의 리스트
    Notion API가 한 번에 100개까지만 추가 가능하므로 100개씩 나눠서 전송합니다."""
    children = [_block(it["type"], it["text"]) for it in items]
    for i in range(0, len(children), 100):
        r = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
            json={"children": children[i:i+100]},
        )
        r.raise_for_status()
    return {"ok": True, "added": len(children)}


def notion_update_block(block_id: str, type: str, text: str):
    """기존 블록의 텍스트를 수정.
    block_id: 수정할 블록 ID (get_page_blocks로 먼저 조회 필요)
    type: 블록 유형 (기존 블록의 type과 동일해야 함)
    text: 새로 덮어쓸 텍스트 내용"""
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=NOTION_HEADERS,
        json={type: {"rich_text": _rt(text)}},
    )
    r.raise_for_status()
    return {"ok": True, "id": block_id}


def notion_delete_block(block_id: str):
    """블록 삭제. 삭제된 블록은 복구할 수 없으므로 주의."""
    r = requests.delete(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=NOTION_HEADERS,
    )
    r.raise_for_status()
    return {"ok": True, "id": block_id}


def notion_insert_after(page_id: str, after_block_id: str, items: list):
    """특정 블록 바로 뒤에 새 블록들을 삽입.
    after_block_id: 이 블록 뒤에 삽입됨
    items: [{"type": "paragraph", "text": "내용"}, ...] 형태의 리스트"""
    children = [_block(it["type"], it["text"]) for it in items]
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=NOTION_HEADERS,
        json={"children": children, "after": after_block_id},
    )
    r.raise_for_status()
    return {"ok": True, "inserted": len(children)}


# ========== LLM에 전달할 툴 스키마 정의 ==========
# Claude가 호출할 수 있는 도구(Function) 목록을 OpenAI Tool-Use 형식으로 정의합니다.
# Claude는 사용자 지시를 분석한 뒤, 아래 도구 중 적절한 것을 선택하여 호출합니다.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_page_blocks",
            "description": "현재 Notion 페이지의 모든 블록을 id/type/text 형태로 반환. 수정 전에 반드시 먼저 호출해서 block_id를 파악할 것.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_blocks",
            "description": "페이지 맨 끝에 새 블록들을 추가.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]},
                                "text": {"type": "string"},
                            },
                            "required": ["type", "text"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_block",
            "description": "기존 블록의 텍스트를 교체. type은 기존 블록의 type과 동일해야 함(타입 변경은 delete 후 insert_after 사용).",
            "parameters": {
                "type": "object",
                "properties": {
                    "block_id": {"type": "string"},
                    "type": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["block_id", "type", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_block",
            "description": "블록 삭제.",
            "parameters": {
                "type": "object",
                "properties": {"block_id": {"type": "string"}},
                "required": ["block_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_after",
            "description": "특정 블록 바로 뒤에 새 블록들을 삽입.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_block_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["type", "text"],
                        },
                    },
                },
                "required": ["after_block_id", "items"],
            },
        },
    },
]

# 툴 이름 → 실제 실행 함수 매핑 (Claude가 도구를 호출하면 여기서 실제 함수를 찾아 실행)
TOOL_IMPL = {
    "get_page_blocks": lambda **kw: notion_get_page_blocks(PAGE_ID),
    "append_blocks":   lambda **kw: notion_append_blocks(PAGE_ID, kw["items"]),
    "update_block":    lambda **kw: notion_update_block(kw["block_id"], kw["type"], kw["text"]),
    "delete_block":    lambda **kw: notion_delete_block(kw["block_id"]),
    "insert_after":    lambda **kw: notion_insert_after(PAGE_ID, kw["after_block_id"], kw["items"]),
}


# ========== Agent 메인 루프 ==========
# 시스템 프롬프트: Claude에게 역할과 작업 규칙을 지시합니다.
SYSTEM_PROMPT = """You are an academic writing assistant with direct access to a Notion research-methodology page via tools.

Workflow:
1. Before any edit, call get_page_blocks to see current block IDs and content.
2. Plan minimal edits: prefer update_block over delete+insert when possible.
3. After edits, briefly report what you changed in Korean.

Style rules:
- IEEE-style academic tone, preserve technical terminology.
- Reply to the user in Korean unless told otherwise.
- For destructive ops (delete, bulk update), state your plan first and confirm before executing if the user's instruction is ambiguous.
"""


def run_agent(user_msg, history):
    """사용자 메시지를 받아 Claude에게 전달하고, 도구 호출 루프를 실행.
    Claude가 도구를 호출하면 실제 Notion API를 실행한 뒤 결과를 다시 전달합니다.
    도구 호출이 없으면 (= 최종 응답) 대화를 종료합니다."""
    history.append({"role": "user", "content": user_msg})

    # 한 턴당 최대 15회까지 도구 호출 허용 (무한루프 방지)
    for step in range(15):
        # LLM에 대화 이력과 도구 목록을 전달하여 응답 생성
        resp = llm.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=TOOLS,
            max_tokens=4096,
        )
        msg = resp.choices[0].message
        history.append(msg.model_dump(exclude_none=True))

        # 도구 호출이 없으면 최종 텍스트 응답 → 출력 후 종료
        if not msg.tool_calls:
            print(f"\n🤖 {msg.content}")
            return history

        # Claude가 호출한 도구들을 순서대로 실행
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"   🔧 {name}({', '.join(f'{k}=...' for k in args)})")
            try:
                # 도구 이름으로 실제 함수를 찾아 실행
                result = TOOL_IMPL[name](**args)
                content = json.dumps(result, ensure_ascii=False)
            except Exception as e:
                # 에러 발생 시 에러 메시지를 Claude에게 다시 전달
                content = json.dumps({"error": str(e)}, ensure_ascii=False)
                print(f"      ❌ {e}")
            # 도구 실행 결과를 대화 이력에 추가 (Claude가 결과를 보고 다음 행동 결정)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

    print("⚠️ 최대 툴 호출 횟수 도달")
    return history


def main():
    """CLI 대화 루프. 사용자로부터 여러 줄 입력을 받아 에이전트에 전달합니다.
    'done'을 입력하면 지시 제출, 'exit'를 입력하면 프로그램 종료."""
    print(f"🤖 {MODEL} + Notion tool-use agent")
    print(f"📄 Page: {PAGE_ID}")
    print("💬 자유롭게 지시하세요. 종료: exit / 여러 줄 입력 제출: done\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        print("=" * 40)
        print("📝 지시 (제출: done / 종료: exit)")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not lines and line.strip().lower() == "exit":
                return
            if line.strip().lower() == "done":
                break
            lines.append(line)
        user_msg = "\n".join(lines).strip()
        if not user_msg:
            continue
        if user_msg.lower() == "exit":
            return

        history = run_agent(user_msg, history)


if __name__ == "__main__":
    main()

