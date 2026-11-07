from fastapi import APIRouter

from app.api.v1.activity import router as activity_router
from app.api.v1.brand_intelligence import router as brand_intelligence_router
from app.api.v1.business_context import router as business_context_router
from app.api.v1.business_products import router as business_products_router
from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.content import router as content_router
from app.api.v1.drafts import router as drafts_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.usage import router as usage_router
from app.api.v1.billing import router as billing_router
from app.api.v1.platform_admin import router as platform_admin_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.social_accounts import router as social_accounts_router
from app.api.v1.tiktok_publishing import router as tiktok_publishing_router
from app.api.v1.youtube_publishing import router as youtube_publishing_router
from app.api.v1.facebook_publishing import router as facebook_publishing_router
from app.api.v1.scheduling import router as scheduling_router
from app.api.v1.media_assets import router as media_assets_router
from app.api.v1.facebook_oauth import router as facebook_oauth_router, callback_router as facebook_oauth_callback_router
from app.api.v1.social_oauth import router as social_oauth_router, callback_router as social_oauth_callback_router, tiktok_callback_router, youtube_callback_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(brand_intelligence_router)
router.include_router(organizations_router)
router.include_router(profiles_router)
router.include_router(social_accounts_router)
router.include_router(facebook_oauth_router)
router.include_router(facebook_oauth_callback_router)
router.include_router(social_oauth_router)
router.include_router(social_oauth_callback_router)
router.include_router(tiktok_callback_router)
router.include_router(youtube_callback_router)
router.include_router(tiktok_publishing_router)
router.include_router(youtube_publishing_router)
router.include_router(facebook_publishing_router)
router.include_router(scheduling_router)
router.include_router(media_assets_router)
router.include_router(business_products_router)
router.include_router(business_context_router)
router.include_router(categories_router)
router.include_router(content_router)
router.include_router(drafts_router)
router.include_router(activity_router)
router.include_router(usage_router)
router.include_router(billing_router)
router.include_router(platform_admin_router)


@router.get("/", tags=["system"])
def api_root() -> dict[str, str]:
    return {"message": "Business Automation Platform API v1"}
