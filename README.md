# AI efficiency study — prototype

A local prototype for a Qualtrics study. Participants open the same chat page, chat in one continuous conversation, select **I'm finished**, and copy a unique five-digit completion code back to Qualtrics. Qualtrics holds the task, condition and survey; join its responses with `completion_code` from the export.

## Run locally

Requires Python 3.9 or newer; no packages needed.

```sh
python3 app.py
```

Open http://localhost:8000. Without an API key, responses are simulated and the page explicitly says so. For real chat, set `OPENAI_API_KEY` in your environment and optionally `OPENAI_MODEL` (default `gpt-4o-mini`) before running. The API key stays on the server. API calls may incur charges. Set `CODE_MIN` and `CODE_MAX` to change the inclusive completion-code range (defaults 11111–22222). Use a fresh database for each study. The default database is `study.db`; set `STUDY_DB` to change the path. Do not commit data or secrets.

The browser retains the session token locally, so a refresh restores the conversation and code. To simulate a new participant use a private browser window or a separate browser profile. The timer starts when the server creates the session on page load; it does not include time spent in Qualtrics. Finish is irreversible. A code is only issued at finish.

## Export

Stop the server before exporting for a consistent snapshot, then run `python3 export.py exports`. The output includes `sessions.csv`, `messages.csv`, `events.csv`, and `summary.csv`. Session IDs are secret bearer tokens: keep exports private. Raw timestamps are UTC. Elapsed seconds are from session creation to completion; incomplete sessions have no elapsed value. Follow-up count is user messages minus one (minimum zero), not a measure of waste. Token counts are provider-reported per response and summed only if all assistant responses have usage; demo usage is blank. Token counts include repeated conversation context. Cost is not calculated because model prices vary; use the recorded model and usage with the applicable pricing. Events include start, completion, request errors, visibility, page exit and inactivity after 60 seconds without keyboard/pointer input. Events are best-effort browser signals, not proof of attention or abandonment. Open sessions in the export are marked incomplete, not assumed abandoned.

## Important prototype limits

This is a **local prototype, not ready for participant deployment**. SQLite is stored on local disk, which is not durable shared storage on Vercel. Before a real study, add a managed database with transactional unique code allocation, access controls, request and spending limits, backup and retention/deletion policies, secure deployment, monitoring, and a protected researcher export. Review consent, provider data handling and institutional requirements. The prototype does not capture text in other applications, actual task quality, Qualtrics timestamps, or cost. There is no participant authentication and browser storage may be cleared. Test the Qualtrics return flow and define a recovery procedure before launch. Do not use with real participant data until these issues are addressed.
