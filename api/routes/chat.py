import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from core.orchestrator import TravelOrchestrator
from core.skills import list_skills
from data.redis_memory import RedisUnavailableError
from models.schemas import ChatRequest, ChatResponse, ChatMetadata
from utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["chat"])
logger = get_logger("travel_assistant.api")

_orchestrator: TravelOrchestrator | None = None


def get_orchestrator() -> TravelOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TravelOrchestrator()
    return _orchestrator


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        session, result = get_orchestrator().run(
            user_id=request.user_id,
            user_message=request.message,
            session_id=request.session_id,
            skills=request.skills,
        )
    except RedisUnavailableError as exc:
        logger.error("chat failed due to redis | session=%s error=%s", request.session_id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("chat failed | session=%s", request.session_id)
        raise HTTPException(status_code=500, detail=f"chat failed: {exc}") from exc

    return ChatResponse(
        response=result.answer,
        session_id=session.session_id,
        sources=result.sources,
        suggested_actions=result.follow_up_questions,
        metadata=ChatMetadata(
            intent=result.intent,
            confidence=result.confidence,
            agent_sequence=result.agent_sequence,
            tool_calls=result.tool_calls,
            trip_summary=result.trip_summary,
            rich_content=result.rich_content,
            debug={
                "session_id": session.session_id,
                "agent_details": result.agent_details,
                "message_count": len(session.messages),
                "trip_profile": session.trip_profile.model_dump(),
                "tool_memory": session.tool_memory,
            },
        ),
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        yield {"event": "start", "data": json.dumps({"status": "started"})}
        try:
            session, result = get_orchestrator().run(
                user_id=request.user_id,
                user_message=request.message,
                session_id=request.session_id,
                skills=request.skills,
            )
            payload = ChatResponse(
                response=result.answer,
                session_id=session.session_id,
                sources=result.sources,
                suggested_actions=result.follow_up_questions,
                metadata=ChatMetadata(
                    intent=result.intent,
                    confidence=result.confidence,
                    agent_sequence=result.agent_sequence,
                    tool_calls=result.tool_calls,
                    trip_summary=result.trip_summary,
                    rich_content=result.rich_content,
                    debug={
                        "session_id": session.session_id,
                        "agent_details": result.agent_details,
                        "message_count": len(session.messages),
                        "trip_profile": session.trip_profile.model_dump(),
                        "tool_memory": session.tool_memory,
                    },
                ),
            )
            yield {"event": "complete", "data": payload.model_dump_json()}
        except RedisUnavailableError as exc:
            logger.error("chat stream failed due to redis | session=%s error=%s", request.session_id, exc)
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
        except Exception as exc:
            logger.exception("chat stream failed | session=%s", request.session_id)
            yield {"event": "error", "data": json.dumps({"detail": f"chat failed: {exc}"})}

    return EventSourceResponse(event_generator())


@router.get("/skills")
async def skills_catalog():
    return {"skills": list_skills()}
