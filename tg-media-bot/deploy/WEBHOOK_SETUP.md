# Webhook setup notes

1. Set `BOT_UPDATE_MODE=webhook`.
2. Set `WEBHOOK_BASE_URL` to your HTTPS domain, for example `https://example.com`.
3. Configure reverse proxy (example in `webhook-nginx.conf`).
4. Ensure `WEBHOOK_PATH` matches the proxy location and app config.
5. Start the bot service and verify webhook with Telegram:

```bash
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
```

If `BOT_UPDATE_MODE=polling`, webhook is removed automatically on startup.
