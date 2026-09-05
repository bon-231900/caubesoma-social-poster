from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import logging
from app.config import get_settings
from app.database import get_due_scheduled_posts, get_post_by_id, update_post, claim_post_for_publish
from app.time_utils import now_utc_iso
from app.meta_service import (
    publish_to_facebook,
    publish_to_instagram,
    publish_facebook_story,
    publish_instagram_story
)
from app.story_service import create_story_image
from app.google_service import publish_to_google_business
from app.threads_service import publish_to_threads
from app.maintenance import backup_database, cleanup_orphaned_media

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def publish_single_post(post_id: int):
    if not claim_post_for_publish(post_id):
        post = get_post_by_id(post_id)
        logger.warning("Post %s is not eligible for publishing", post_id)
        return {"status": post.get("status") if post else "not_found", "error_log": "Bài viết đang được xử lý hoặc đã đăng xong."}
    post = get_post_by_id(post_id)
    if not post:  # Defensive only; a claimed row should always exist.
        logger.error(f"Post {post_id} not found.")
        return

    settings = get_settings()
    page_id = settings.get("fb_page_id")
    page_token = settings.get("fb_page_access_token")
    ig_account_id = settings.get("ig_business_account_id")
    imgbb_key = settings.get("imgbb_api_key")

    fb_success = bool(post.get("fb_post_id"))
    ig_success = bool(post.get("ig_post_id"))
    google_success = bool(post.get("google_post_id"))
    threads_success = bool(post.get("threads_post_id"))
    fb_post_id = post.get("fb_post_id")
    ig_post_id = post.get("ig_post_id")
    google_post_id = post.get("google_post_id")
    threads_post_id = post.get("threads_post_id")
    story_fb_id = post.get("story_fb_id")
    story_ig_id = post.get("story_ig_id")
    story_fb_success = bool(story_fb_id)
    story_ig_success = bool(story_ig_id)
    errors = []

    # 1. Publish Feed Post to Facebook
    if post.get("target_fb") and not fb_success:
        try:
            fb_res = publish_to_facebook(
                page_id=page_id,
                page_token=page_token,
                caption=post.get("fb_caption", ""),
                images=post.get("images", [])
            )
            fb_post_id = fb_res.get("post_id")
            fb_success = True
        except Exception as e:
            errors.append(f"Facebook Feed Error: {str(e)}")

    # 2. Publish Feed Post to Instagram
    if post.get("target_ig") and not ig_success:
        try:
            ig_res = publish_to_instagram(
                ig_account_id=ig_account_id,
                page_token=page_token,
                caption=post.get("ig_caption", ""),
                images=post.get("images", []),
                imgbb_api_key=imgbb_key
            )
            ig_post_id = ig_res.get("post_id")
            ig_success = True
        except Exception as e:
            errors.append(f"Instagram Feed Error: {str(e)}")

    # 3. Publish Stories (Facebook Page & Instagram Story)
    if post.get("target_story"):
        story_img = post.get("story_image")
        if not story_img and post.get("images"):
            try:
                caption_hint = post.get("story_hook") or post.get("fb_caption") or post.get("ig_caption") or ""
                template = post.get("story_template") or "glassmorphism"
                story_link = post.get("story_link") or "https://roots.vn"
                story_img = create_story_image(
                    post["images"][0],
                    caption_hint=caption_hint,
                    template=template,
                    story_link=story_link
                )
                update_post(post_id, story_image=story_img)
            except Exception as e:
                errors.append(f"Story Generation Error: {str(e)}")

        if story_img:
            if post.get("target_fb") and not story_fb_success:
                try:
                    fb_story_res = publish_facebook_story(
                        page_id=page_id,
                        page_token=page_token,
                        story_image_name=story_img,
                        link_url=post.get("story_link"),
                        imgbb_api_key=imgbb_key
                    )
                    story_fb_id = fb_story_res.get("story_id")
                    story_fb_success = True
                except Exception as e:
                    errors.append(f"Facebook Story Error: {str(e)}")

            if post.get("target_ig") and not story_ig_success:
                try:
                    ig_story_res = publish_instagram_story(
                        ig_account_id=ig_account_id,
                        page_token=page_token,
                        story_image_name=story_img,
                        imgbb_api_key=imgbb_key
                    )
                    story_ig_id = ig_story_res.get("story_id")
                    story_ig_success = True
                except Exception as e:
                    errors.append(f"Instagram Story Error: {str(e)}")

    # 4. Publish to Google Business Profile (ROOTS)
    if post.get("target_google") and not google_success:
        try:
            google_summary = post.get("google_caption") or post.get("fb_caption") or post.get("ig_caption") or ""
            google_res = publish_to_google_business(
                summary=google_summary,
                images=post.get("images", []),
                action_type=post.get("google_action_type", "LEARN_MORE"),
                action_url=post.get("google_action_url") or None,
                imgbb_api_key=imgbb_key
            )
            google_post_id = google_res.get("post_id")
            google_success = True
        except Exception as e:
            errors.append(f"Google Business Error: {str(e)}")

    # 5. Publish to Meta Threads (@roots.vn)
    if post.get("target_threads") and not threads_success:
        try:
            threads_text = post.get("threads_caption") or post.get("fb_caption") or post.get("ig_caption") or ""
            threads_res = publish_to_threads(
                text=threads_text,
                images=post.get("images", []),
                topic_tag=post.get("threads_topic_tag"),
                imgbb_api_key=imgbb_key
            )
            threads_post_id = threads_res.get("thread_id")
            threads_success = True
        except Exception as e:
            errors.append(f"Threads Error: {str(e)}")

    # Determine final status
    targets_count = (
        (1 if post.get("target_fb") else 0) +
        (1 if post.get("target_ig") else 0) +
        (1 if post.get("target_google") else 0) +
        (1 if post.get("target_threads") else 0)
    )
    success_count = (
        (1 if fb_success else 0) +
        (1 if ig_success else 0) +
        (1 if google_success else 0) +
        (1 if threads_success else 0)
    )
    if post.get("target_story"):
        if post.get("target_fb"):
            targets_count += 1
            success_count += 1 if story_fb_success else 0
        if post.get("target_ig"):
            targets_count += 1
            success_count += 1 if story_ig_success else 0

    if success_count == targets_count and targets_count > 0:
        final_status = "success"
    elif success_count > 0:
        final_status = "partial_failed"
    else:
        final_status = "failed"

    now_iso = now_utc_iso()
    error_log = "\n".join(errors) if errors else None

    update_post(
        post_id,
        status=final_status,
        published_at=now_iso,
        fb_post_id=fb_post_id,
        ig_post_id=ig_post_id,
        google_post_id=google_post_id,
        threads_post_id=threads_post_id,
        story_fb_id=story_fb_id,
        story_ig_id=story_ig_id,
        error_log=error_log,
        platform_results={
            "facebook_feed": fb_success, "instagram_feed": ig_success,
            "facebook_story": story_fb_success, "instagram_story": story_ig_success,
            "google_business": google_success,
            "threads": threads_success
        }
    )
    return {
        "status": final_status,
        "fb_post_id": fb_post_id,
        "ig_post_id": ig_post_id,
        "google_post_id": google_post_id,
        "threads_post_id": threads_post_id,
        "story_fb_id": story_fb_id,
        "story_ig_id": story_ig_id,
        "error_log": error_log
    }

def check_scheduled_posts():
    now_iso = now_utc_iso()
    due_posts = get_due_scheduled_posts(now_iso)
    for p in due_posts:
        try:
            logger.info(f"Triggering scheduled post {p['id']}")
            publish_single_post(p["id"])
        except Exception as e:
            logger.error(f"Error executing scheduled post {p['id']}: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_scheduled_posts, 'interval', seconds=15, id='check_scheduled_posts', replace_existing=True)
        scheduler.add_job(backup_database, 'cron', hour=2, id='backup_database', replace_existing=True)
        scheduler.add_job(cleanup_orphaned_media, 'cron', hour=3, id='cleanup_orphaned_media', replace_existing=True)
        scheduler.start()
        logger.info("Scheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
