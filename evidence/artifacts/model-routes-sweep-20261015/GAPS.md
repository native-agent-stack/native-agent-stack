# Named gaps and approval-gated measurements

**None of the keyed or inference commands below ran.** They are concrete proposals for CC review. The only executed network route probe was unkeyed `GET /v1/models` on 21128. Even a successful metadata or text smoke is not an upstream full-harness qualification or comparative A6 run.

All credentials in the examples are symbolic inputs for a future explicitly approved execution. This lane did not read those variables or credential files. Output filters exclude account and credential fields. No HTTP trace/debug logging is proposed.

## F5-G-FAMILY

Obtain discover:model-routes, refute-facts:model-routes and refute-fit:model-routes from the Claude family plus critic, using the same immutable scope and exact identity strings. Review and merge through the existing harness.

## F5-G-REQUIREMENT

Owners register the missing research-state requirement and decide the v1 closed-vendor identity adapter; regenerate scope hashes and validate conversion before append.

## F5-G-USAGE

Obtain approved current-lane model/effort/tier and usage metadata without account fields. A later normal child-usage.mjs receipt cannot fabricate an earlier session's usage.

## F5-G-OMNI-PIN

Obtain the deployment owner's public build/patch provenance binding the installed source hashes to a full commit. Public v3.8.51 alone is insufficient.

```sh
gh api repos/diegosouzapw/OmniRoute/commits/2a41147b7 --jq .sha
```

## F5-G-CLIENT

OpenCode version is unverified; Muse version remains the historical fence pin and cannot be executed here. Generic harness candidates need a named client.

```sh
opencode --version
```

## F5-G-TIER

Resolve each provider's service-tier field in current official reference; public API tier and subscription plan are separate.

## F5-G-EFFORT

Pin the missing model/client mapping first; do not infer supported effort from a suffix or another protocol.

## F5-G-PLAN

Use public plan class first; account-specific quota/billing remains private and outside this lane.

## F5-G-ANTHROPIC-MODELS

After approval and key injection, obtain only model/capability fields. This closes account model exposure, not a Messages inference, tool parity or quality gap.

```sh
for model in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5 claude-fable-5-1; do
  curl --fail --silent --show-error "https://api.anthropic.com/v1/models/$model" \
    -H "x-api-key: ${ANTHROPIC_API_KEY:?CC-approved injection required}" \
    -H 'anthropic-version: 2023-06-01' |
    jq '{id, max_input_tokens, max_tokens, capabilities}'
done
```

## F5-G-ANTHROPIC-TIER

Read the current Messages service_tier parameter section; this sweep did not establish it. Do not spend before the documented field and approved tier are fixed.

## F5-G-OMNI-WIRE

After CC approval, probe the three explicit models at max/default. A sanitized gateway trace of outbound model, reasoning.effort and service_tier is additionally required; returned metadata alone cannot prove max reached upstream.

```sh
for model in cx/gpt-6-astra cx/gpt-6.1-sol cx/gpt-6-luna; do
  jq -cn --arg model "$model" '{model:$model,input:"Reply ROUTE_SMOKE_OK.",reasoning:{effort:"max"},service_tier:"default",max_output_tokens:512,store:false}' |
    curl --fail --silent --show-error http://127.0.0.1:21128/v1/responses \
      -H 'Content-Type: application/json' --data-binary @- |
    jq '{model,status,service_tier,usage}'
done
```

## F5-G-LIMITS

The permitted listing already confirms 872000 gateway context/input. API docs show 1050000. Before any expensive boundary probe, preregister two input lengths, output reserve, tokenizer and cost cap; the 512-token smoke cannot settle accepted maximum context.

```sh
curl --fail --silent --show-error http://127.0.0.1:21128/v1/models | jq '[.data[] | select(.id == "cx/gpt-6-astra" or .id == "cx/gpt-6.1-sol" or .id == "cx/gpt-6-luna") | {id,context_length,max_input_tokens,max_output_tokens}]'
```

## F5-G-META-API

Only with a separately entitled Model API key and CC approval. Protocol smokes are measurement probes, not harness qualification. Native Muse remains held even if these pass.

```sh
for model in muse-wonder-1.0 muse-spark-1.3; do
  jq -cn --arg model "$model" '{model:$model,input:"Reply ROUTE_SMOKE_OK.",reasoning:{effort:"max"},max_output_tokens:512}' |
    curl --fail --silent --show-error https://api.meta.ai/v1/responses \
      -H "Authorization: Bearer ${MODEL_API_KEY:?CC-approved independent Model API key required}" \
      -H 'Content-Type: application/json' --data-binary @- |
    jq '{model,status,usage}'
done
```

```sh
curl --fail --silent --show-error https://api.meta.ai/v1/messages \
  -H "Authorization: Bearer ${MODEL_API_KEY:?CC-approved independent Model API key required}" \
  -H 'Content-Type: application/json' -H 'anthropic-version: 2023-06-01' \
  --data '{"model":"muse-wonder-1.0","max_tokens":512,"messages":[{"role":"user","content":"Reply ROUTE_SMOKE_OK."}]}' |
  jq '{model,stop_reason,usage}'
```

```sh
curl --fail --silent --show-error https://api.meta.ai/v1/chat/completions \
  -H "Authorization: Bearer ${MODEL_API_KEY:?CC-approved independent Model API key required}" \
  -H 'Content-Type: application/json' \
  --data '{"model":"muse-wonder-1.0","max_tokens":512,"reasoning_effort":"max","messages":[{"role":"user","content":"Reply ROUTE_SMOKE_OK."}]}' |
  jq '{model,usage,finish_reasons:[.choices[].finish_reason]}'
```

## F5-G-MUSE-ID

Only after HOLD resolution, both required fence reviews, exact runtime/argv approval and a fresh ordinary-.git clone plus the named nonsecret brief exist. The command starts the existing fence; none of its internal launcher steps ran here. A successful native receipt does not qualify OmniRoute's muse-code provider.

```sh
systemd-run --user --scope -p CPUWeight=idle --quiet -- \
  python3 tools/muse_file_fence.py --role reader --max-model-steps 1 --timeout 180 \
  /var/tmp/model-routes-f5-native /var/tmp/model-routes-f5-brief.md /var/tmp/model-routes-f5-logs
```

## F5-G-MUSE-FOREIGN

Current Model API terms section 3.2 and Wonder availability retain the carried rejection. Require a new supported route/entitlement source; no keyed bypass measurement is proposed.

## F5-G-OPENAI-FOREIGN

Name the non-Codex client and supported per-user sign-in/deployment model. No unspecified pooled-route probe is approved or sufficient.

## F5-G-SPARK-CONTRIBUTOR

Gateway lists max for Spark 1.3 Contributor; Meta says it is unsupported. Confirm against a newer supported upstream release or obtain an approved independent API negative test. Contributor mode is outside this sweep; no call proposed now.

The native Muse command additionally requires `/var/tmp/model-routes-f5-native` to be a fresh dedicated ordinary Git clone, `/var/tmp/model-routes-f5-brief.md` to be a named reviewed nonsecret input and the log directory to be absent. The existing fence enforces its fixed model/effort and contributor-off/web-tools-disabled argv. This document neither lifts the HOLD nor grants a directory or role.

## F5-G-SONNET-CACHE

The installed claude-api skill says $0.20 per MTok for Sonnet 5.5 cache reads; the fetched live pricing page gives 0.05x base input, which is $0.10 at the documented $2 base. The rate stays UNVERIFIED pending reconciliation of the model-specific pricing row or vendor correction. A token-usage smoke alone cannot establish a dollar rate, so no new paid probe is proposed for this gap.
