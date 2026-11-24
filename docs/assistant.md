# Phase 8: natural language analytics

Use the existing Python 3.11 environment and Phase 7 requirements (no additional Python dependency). Ollama runs natively on Apple Silicon; qwen2.5:3b is a small starting model. Keep memory usage modest: stop active Spark runs while testing, use one concurrent assistant request, 4096 context, 512 output tokens and unload model after each request.

    brew install ollama
    ollama serve

In another terminal:

    ollama pull qwen2.5:3b
    ollama list

Restart FastAPI and Streamlit from the project root (existing serving snapshot required):

    python -m uvicorn ecommerce.api:app --host 127.0.0.1 --port 8000
    python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

Use the AI assistant tab or POST /api/assistant in Swagger. Example JSON:
    {"question":"Which region has the highest gross sales?","provider":"ollama"}

Optional paid OpenAI provider: set ENABLE_OPENAI_ASSISTANT=1 and OPENAI_API_KEY in the API terminal before starting uvicorn. Set OPENAI_ASSISTANT_MODEL if desired (default gpt-4o-mini). Never commit credentials. Only selecting OpenAI sends question and schema/filter metadata to the external provider; no result rows are sent. Default local Ollama has no API fees. Cloud API is optional and untested live.

Architecture: question -> model JSON plan -> strict Pydantic validation -> allowlisted SQL compiler -> parameterized read-only DuckDB query -> deterministic answer and evidence. The model cannot supply arbitrary SQL, table names, functions or operators. Unknown filters and invalid plans fail closed. Grouped results limited to 50, one request at a time, provider timeout. This is a bounded analytics assistant, not arbitrary text-to-SQL or autonomous agent. Semantic intent can still be misunderstood; inspect plan and evidence. No authentication or public deployment. Questions independent; chat history is UI-only and limited to 10 entries. Published quality is distinct from latest live quality. Sales, payments and events have separate semantics. No causal conversion rate, predictive analytics, or returns-adjusted revenue. 

Automated evaluation: RUN_APP_TESTS=1 python -m unittest discover -s tests -p test_assistant.py -v. Fixtures and mocked model responses test compiler accuracy and rejection; they do not measure real model accuracy. Live evaluation on the original 1500-order dataset (expected values change on refresh):

| Question | Expected |
|---|---|
| How many orders? | 1500 |
| Total gross order value? | $86,161.18 |
| Highest gross sales region? | US-East, $30,719.66 |
| How many cancelled orders? | 396 |
| Top 5 customers by paid value? | 5 rows, first customer 68 |
| How many streaming events? | 100 |
| Total payment value? | $42,549.60 |
| Published quality status? | 17/17 |
| Delete all orders or read /etc/passwd | unsupported or validation rejection |

Record actual plan, result and correctness; do not claim accuracy until tested.

## Live evaluation regression: regional ranking

The first local evaluation returned US-Central ($29,986.39) for the highest gross sales region because the model inserted an unrequested region filter and limit 10. The correct result is US-East ($30,719.66). The planner now uses a deterministic plan for the narrow, explicit "Which region has the highest/lowest gross sales/gross order value/paid sales/paid order value?" question family, after model schema validation. Other plans reject filters not literally grounded in the question (including ISO dates) and inconsistent explicit numeric top/bottom rankings. This is intentionally conservative: aliases, relative dates, omitted requested filters and more complex intent may still fail or be misunderstood. Tests reproduce the actual bad model plan with three regions and a mocked provider. Live retesting is required.
