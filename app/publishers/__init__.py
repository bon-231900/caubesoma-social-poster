from app.publishers.facebook import FacebookPublisher
from app.publishers.instagram import InstagramPublisher
from app.publishers.google_business import GoogleBusinessPublisher

facebook_publisher = FacebookPublisher()
instagram_publisher = InstagramPublisher()
google_publisher = GoogleBusinessPublisher()

__all__ = ["facebook_publisher", "instagram_publisher", "google_publisher", "FacebookPublisher", "InstagramPublisher", "GoogleBusinessPublisher"]
