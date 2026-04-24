# notion-api-agent
시립대 AI chat 활용 노션 에이전트 만들기

## 개요
이 프로젝트는 Claude와 Notion API를 활용하여 사용자가 내린 지시에 따라 지정된 Notion 페이지를 직접 읽고, 쓰고, 수정할 수 있는 에이전트 스크립트(`notion_editor_claude.py`)를 제공합니다. 시스템 프롬프트 상에서는 학술적인 톤(IEEE 스타일)을 유지하고 피드백을 전달하도록 설정되어 있어, 연구 방법론이나 논문 초안 등을 Notion에 작성할 때 유용하게 활용할 수 있습니다.

## 주요 기능 (Agent 툴 기능)
- **페이지 구조 파악 (`get_page_blocks`)**: 현재 Notion 페이지의 전체 블록(텍스트, 제목 등)과 ID를 읽어옵니다.
- **블록 추가 (`append_blocks`)**: 페이지 맨 하단에 새로운 블록들을 생성합니다.
- **블록 수정 (`update_block`)**: 특정 블록의 기존 내용을 교체 및 수정합니다.
- **블록 삭제 (`delete_block`)**: 불필요한 블록을 지정하여 삭제합니다.
- **특정 위치에 삽입 (`insert_after`)**: 특정 블록의 바로 다음 위치에 새 블록들을 삽입합니다.

## 설치 및 설정 가이드

### 1. 필수 라이브러리 설치
다음 Python 패키지들을 설치해야 합니다:
```bash
pip install requests python-dotenv openai
```

### 2. 환경 변수 설정
프로젝트 최상단 폴더에 `.env` 파일을 생성하고, 아래의 3가지 키 값을 입력합니다:
```env
NOTION_TOKEN=당신의_노션_토큰_입력
PAGE_ID=작업할_노션_페이지_ID_입력
AICHAT_KEY=당신의_AICHAT_API_키_입력
```
- **NOTION_TOKEN**: 노션 개발자 페이지(https://www.notion.so/my-integrations)에서 발급받은 프라이빗 API 토큰입니다. (페이지에 Integration을 초대해 두어야 합니다.)
- **PAGE_ID**: 편집할 노션 페이지의 고유 ID입니다. (URL 참고)
- **AICHAT_KEY**: 시립대 AI Chat(Mindlogic API)을 이용하기 위한 API 키입니다.

## 실행 방법

아래 명령어를 통해 스크립트를 실행합니다:
```bash
python notion_editor_claude.py
```

### 상호작용 방법
1. 프로그램을 실행하면 콘솔에서 지시를 입력할 수 있습니다. 
2. 여러 줄의 명령을 입력하는 것이 가능합니다.
3. 입력이 완료되었다면 새 줄에 **`done`** 이라고 입력하고 엔터를 누르면 Agent가 작업을 시작하고 Notion에 반영합니다.
4. 프로그램을 완전히 종료하려면 **`exit`** 이라고 입력하면 됩니다.
