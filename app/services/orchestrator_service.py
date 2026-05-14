import uuid
from app.agents.intent_agent import intent_agent
from app.agents.content_agent import content_agent
from app.services.publishing_service import publishing_service


class OrchestratorService:

    def process(self, user_id: str, message: str):

        # 1. Understand user intent
        intent = intent_agent.parse(message)

        # 2. Generate caption + image
        caption = content_agent.generate_caption(intent)
        image_url = content_agent.generate_image(intent)

        # 3. Create pending job (WAIT FOR USER CONFIRMATION)
        job_id = publishing_service.create_pending_job(
            user_id=user_id,
            caption=caption,
            image_url=image_url,
            platforms=intent.get("platforms", ["instagram"])
        )

        # 4. Return preview to WhatsApp
        return {
            "status": "pending_confirmation",
            "job_id": job_id,
            "caption": caption,
            "image_url": image_url,
            "message": "Do you want to post this on Instagram + LinkedIn? Reply YES or NO"
        }


orchestrator_service = OrchestratorService()