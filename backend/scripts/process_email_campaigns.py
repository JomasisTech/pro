"""Run once from backend/ on a scheduler: python -m scripts.process_email_campaigns"""
from app.modules.platform_admin.email_campaign_worker import process_email_campaigns

if __name__ == "__main__":
    print(process_email_campaigns(batch_size=100))
