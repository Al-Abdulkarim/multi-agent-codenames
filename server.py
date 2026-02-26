"""
خادم الويب - Web Server
FastAPI backend مع WebSocket للتواصل المباشر
"""

import json
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

# Fix module resolution for paths with Arabic/Unicode characters
# ملاحظة: يتم تحديد المسارات عبر run.py لضمان التوافق مع أنظمة ويندوز

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import GameConfig, BoardSize, Difficulty, TeamColor, PlayerRole
from game_orchestrator import GameOrchestrator
from evaluation import EvaluationFramework


# ============= إدارة الألعاب النشطة =============

active_games: dict[str, GameOrchestrator] = {}
eval_framework = EvaluationFramework()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق"""
    print("🎮 بدء تشغيل خادم لعبة Codenames العربية...")
    yield
    print("⏹️ إيقاف الخادم...")


app = FastAPI(
    title="Codenames Arabic - نظام لعبة الأسماء الحركية",
    description="نظام متكامل للعبة Codenames العربية مع وكلاء AI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# خدمة الملفات الثابتة
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============= نماذج الطلبات =============


class NewGameRequest(BaseModel):
    board_size: int = 25
    difficulty: str = "medium"
    human_team: str = "red"
    human_role: str = "operative"
    api_key: Optional[str] = None


class ClueRequest(BaseModel):
    game_id: str
    clue: str
    number: int


class GuessRequest(BaseModel):
    game_id: str
    word: str


class PassRequest(BaseModel):
    game_id: str


# ============= المسارات =============


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """تجنب خطأ 404 المزعج في السجلات"""
    return HTMLResponse(content="", status_code=204)


@app.get("/", response_class=HTMLResponse)
async def root():
    """الصفحة الرئيسية"""
    return FileResponse("static/index.html")


@app.post("/api/game/new")
async def new_game(request: NewGameRequest):
    """بدء لعبة جديدة"""
    try:
        # تحويل حجم اللوحة
        size_map = {
            8: BoardSize.SMALL,
            16: BoardSize.MEDIUM,
            25: BoardSize.LARGE,
        }
        board_size = size_map.get(request.board_size, BoardSize.LARGE)

        # تحويل المستوى
        diff_map = {
            "easy": Difficulty.EASY,
            "medium": Difficulty.MEDIUM,
            "hard": Difficulty.HARD,
        }
        difficulty = diff_map.get(request.difficulty, Difficulty.MEDIUM)

        # تحويل الفريق
        team_map = {"red": TeamColor.RED, "blue": TeamColor.BLUE}
        human_team = team_map.get(request.human_team, TeamColor.RED)

        # تحويل الدور
        role_map = {
            "spymaster": PlayerRole.SPYMASTER,
            "operative": PlayerRole.OPERATIVE,
        }
        human_role = role_map.get(request.human_role, PlayerRole.OPERATIVE)

        config = GameConfig(
            board_size=board_size,
            ai_difficulty=difficulty,
            human_team=human_team,
            human_role=human_role,
        )

        if request.api_key:
            config.google_api_key = request.api_key

        if not config.google_api_key:
            detail = "يرجى إدخال مفتاح Google API"
            raise HTTPException(status_code=400, detail=detail)

        orchestrator = GameOrchestrator(config)

        # 1. تهيئة اللعبة والحصول على الكلمات
        start_data = await orchestrator.start_game_initial()
        game_id = start_data["game_id"]

        # 2. إعداد وظيفة البث
        async def broadcast_update(state_data: dict):
            await manager.broadcast(game_id, state_data)

        orchestrator.on_update = broadcast_update

        # 3. حفظ اللعبة في القائمة النشطة
        active_games[game_id] = orchestrator

        # 4. تشغيل الذكاء الاصطناعي في الخلفية مع مهلة بسيطة لاتصال الـ WS
        async def delayed_start():
            await asyncio.sleep(2)
            await orchestrator._run_auto_turns()

            # تسجيل النتيجة إذا انتهت اللعبة بعد الأدوار التلقائية
            if orchestrator.game_state and orchestrator.game_state.game_over:
                eval_framework.record_game(orchestrator)

        asyncio.create_task(delayed_start())

        print(f"DEBUG: Game initialized: {game_id}")
        return orchestrator._get_game_status()

    except Exception as e:
        print(f"ERROR in new_game: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/clue")
async def submit_clue(request: ClueRequest):
    """تقديم شفرة"""
    print(f"DEBUG: Clue submission for {request.game_id}: {request.clue}")
    orchestrator = active_games.get(request.game_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="اللعبة غير موجودة")

    result = await orchestrator.submit_human_clue(request.clue, request.number)
    if "error" in result and not result.get("game_id"):
        print(f"DEBUG: Clue error: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/api/game/guess")
async def submit_guess(request: GuessRequest):
    """تقديم تخمين"""
    orchestrator = active_games.get(request.game_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="اللعبة غير موجودة")

    result = await orchestrator.submit_human_guess(request.word)

    # تسجيل النتيجة إذا انتهت اللعبة
    if orchestrator.game_state and orchestrator.game_state.game_over:
        eval_framework.record_game(orchestrator)

    if "error" in result and not result.get("game_id"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/api/game/pass")
async def pass_turn(request: PassRequest):
    """تمرير الدور"""
    orchestrator = active_games.get(request.game_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="اللعبة غير موجودة")

    result = await orchestrator.pass_turn()
    return result


@app.get("/api/game/{game_id}/status")
async def get_game_status(game_id: str):
    """الحصول على حالة اللعبة"""
    orchestrator = active_games.get(game_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="اللعبة غير موجودة")

    return orchestrator._get_game_status()


@app.get("/api/evaluation/metrics")
async def get_evaluation_metrics():
    """الحصول على مقاييس التقييم"""
    return eval_framework.get_metrics().model_dump()


@app.get("/api/evaluation/report")
async def get_evaluation_report():
    """الحصول على تقرير التقييم"""
    return {"report": eval_framework.get_summary_report()}


# ============= WebSocket للتحديثات المباشرة =============


class ConnectionManager:
    """إدارة اتصالات WebSocket"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            self.active_connections[game_id].remove(websocket)

    async def broadcast(self, game_id: str, message: dict):
        if game_id in self.active_connections:
            for connection in self.active_connections[game_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await manager.connect(websocket, game_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            orchestrator = active_games.get(game_id)
            if not orchestrator:
                await websocket.send_json({"error": "اللعبة غير موجودة"})
                continue

            action = message.get("action")

            if action == "clue":
                result = await orchestrator.submit_human_clue(
                    message.get("clue", ""), message.get("number", 1)
                )
                await manager.broadcast(game_id, result)

            elif action == "guess":
                word = message.get("word", "")
                result = await orchestrator.submit_human_guess(word)
                await manager.broadcast(game_id, result)

            elif action == "pass":
                result = await orchestrator.pass_turn()
                await manager.broadcast(game_id, result)

            elif action == "status":
                result = orchestrator._get_game_status()
                await websocket.send_json(result)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)


# ============= تشغيل الخادم =============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
