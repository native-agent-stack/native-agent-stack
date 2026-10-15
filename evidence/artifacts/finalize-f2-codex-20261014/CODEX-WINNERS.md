# Frozen winners and Codex consumers

Inventory: 252babe4040e39173cc178317c67699371806df6, 57 unique component IDs. Includes every winner so exclusion of a runtime/service/Claude/skill-loader role is explicit. Codex-side callable winners are the six enabled winner MCP registrations, the native client, and the named CLI/hook roles. No consumer field was found in the inspected frozen landscape and installation tables; current Codex registration proves only its MCP consumers. The CC consumer-scoped zero rule applies only to a slot that explicitly names Codex. A zero in incomplete CLI instrumentation is not a proved execution zero. Alias rows use the same observation, and their counts must not be summed.

| Winner | Consumer/scope reasoning | Eligible/observed calls | Frozen run | Host version | Disposition | Artifact |
| --- | --- | ---: | --- | --- | --- | --- |
| affaan-m/ECC | skill-loader role | unknown | dd6ee538aee0f548d4a6b520118f875431fd749e | unverified/not this client | other-consumer | reasons/not-invoked-affaan-m-ecc.json |
| agent-browser | Codex shell/CLI role | unknown | 0.38.2 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-agent-browser.json |
| ai-memory | Codex MCP registration | 0 | 2.4.1 | 2.6.3 | codex-dispatch-wiring-flag | reasons/not-invoked-ai-memory.json |
| candidate:actions-attest | runtime/service/CI consumer | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-candidate-actions-attest.json |
| candidate:astral-sh-uv | Codex shell/CLI role | unknown | 0.12.17 | 0.12.22 | cli-attribution-gap | reasons/not-invoked-candidate-astral-sh-uv.json |
| candidate:cli-cli | Codex shell/CLI role | unknown | 2.101.0 | 2.102.0 | cli-attribution-gap | reasons/not-invoked-candidate-cli-cli.json |
| candidate:openai-skills | skill-loader role | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-candidate-openai-skills.json |
| candidate:typesafe-ai-skills | skill-loader role | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-candidate-typesafe-ai-skills.json |
| ccusage | Codex shell/CLI role | unknown | 20.0.26 | 20.0.26 | cli-attribution-gap | reasons/not-invoked-ccusage.json |
| claude-code | runtime/service/CI consumer | unknown | 2.1.295 | unverified/not this client | other-consumer | reasons/not-invoked-claude-code.json |
| codex | Codex client | unknown | 0.160.0 | 0.162.1 | host-run-drift | reasons/not-invoked-codex.json |
| codex-native-sdk | runtime SDK caller | unknown | 0.160.0 | 0.162.1 | other-consumer-attribution-gap | reasons/not-invoked-codex-native-sdk.json |
| dagu | Codex shell/CLI role | unknown | 2.16.6 | 2.18.2 | cli-attribution-gap | reasons/not-invoked-dagu.json |
| data-alpaca-py | runtime/service/CI consumer | unknown | 0.44.0 | unverified/not this client | other-consumer | reasons/not-invoked-data-alpaca-py.json |
| data-duckdb | runtime/service/CI consumer | unknown | 1.5.5 | unverified/not this client | other-consumer | reasons/not-invoked-data-duckdb.json |
| data-dvc | runtime/service/CI consumer | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-data-dvc.json |
| data-edgartools | runtime/service/CI consumer | unknown | 5.61.1 | unverified/not this client | other-consumer | reasons/not-invoked-data-edgartools.json |
| data-exchange-calendars | runtime/service/CI consumer | unknown | 4.13.2 | unverified/not this client | other-consumer | reasons/not-invoked-data-exchange-calendars.json |
| data-mlflow | runtime/service/CI consumer | unknown | 3.16.1 | unverified/not this client | other-consumer | reasons/not-invoked-data-mlflow.json |
| data-pandera | runtime/service/CI consumer | unknown | 0.33.1 | unverified/not this client | other-consumer | reasons/not-invoked-data-pandera.json |
| difftastic | Codex shell/CLI role | unknown | 0.71.0 | 0.71.0 | cli-attribution-gap | reasons/not-invoked-difftastic.json |
| fastapi | runtime/service/CI consumer | unknown | 0.141.1 | unverified/not this client | other-consumer | reasons/not-invoked-fastapi.json |
| foundation-agent-retrieval-bench | runtime/service/CI consumer | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-foundation-agent-retrieval-bench.json |
| foundation-ai-memory | Codex MCP registration | 0 | 2.4.1 | 2.6.3 | codex-dispatch-wiring-flag | reasons/not-invoked-foundation-ai-memory.json |
| foundation-socraticode | Codex MCP registration | 64 | 1.15.0 | 1.16.0 | invoke-pending-registration | receipts/invoke-foundation-socraticode.json |
| gitleaks | Codex shell/CLI role | unknown | 8.30.1 | 8.30.1 | cli-attribution-gap | reasons/not-invoked-gitleaks.json |
| grype | runtime/service/CI consumer | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-grype.json |
| headroom | Codex MCP registration | 0 | 0.40.0 | 0.40.0 | codex-dispatch-wiring-flag | reasons/not-invoked-headroom.json |
| inspect-ai | runtime/service/CI consumer | unknown | NO RUN | unverified/not this client | other-consumer | reasons/not-invoked-inspect-ai.json |
| lean | runtime/service/CI consumer | unknown | 985ef30 with documented dependency remediation | unverified/not this client | other-consumer | reasons/not-invoked-lean.json |
| loki | runtime/service/CI consumer | unknown | 3.7.8 | unverified/not this client | other-consumer | reasons/not-invoked-loki.json |
| markitdown | Codex shell/CLI role | unknown | 0.1.8 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-markitdown.json |
| mcp-inspector | Codex shell/CLI role | unknown | 2.9.0 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-mcp-inspector.json |
| mcporter | Codex shell/CLI role | unknown | 0.14.2 | 0.14.2 | cli-attribution-gap | reasons/not-invoked-mcporter.json |
| nautilustrader | runtime/service/CI consumer | unknown | 2.0.0rc5 | unverified/not this client | other-consumer | reasons/not-invoked-nautilustrader.json |
| nextjs | runtime/service/CI consumer | unknown | 16.3.8 | unverified/not this client | other-consumer | reasons/not-invoked-nextjs.json |
| openresearch | Codex shell/CLI role | unknown | 0.2.15 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-openresearch.json |
| opentelemetry-collector-contrib | runtime/service/CI consumer | unknown | 0.162.0 | unverified/not this client | other-consumer | reasons/not-invoked-opentelemetry-collector-contrib.json |
| playwright-test | Codex shell/CLI role | unknown | 1.63.0 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-playwright-test.json |
| poppler | Codex shell/CLI role | unknown | 26.09.0 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-poppler.json |
| postgresql | runtime/service/CI consumer | unknown | 18.6 | unverified/not this client | other-consumer | reasons/not-invoked-postgresql.json |
| prometheus | runtime/service/CI consumer | unknown | 3.15.0 | unverified/not this client | other-consumer | reasons/not-invoked-prometheus.json |
| promptfoo | Codex MCP registration | 0 | 0.123.1 | 0.124.0 | codex-dispatch-wiring-flag | reasons/not-invoked-promptfoo.json |
| qdrant | runtime/service/CI consumer | unknown | 1.19.1 | unverified/not this client | other-consumer | reasons/not-invoked-qdrant.json |
| qmd | Codex MCP registration | 0 | 2.8.3 | 2.8.3 | codex-dispatch-wiring-flag | reasons/not-invoked-qmd.json |
| restic | Codex shell/CLI role | unknown | 0.19.1 | 0.19.1 | cli-attribution-gap | reasons/not-invoked-restic.json |
| rtk | Codex shell/CLI role | unknown | 0.51.0 | 0.51.0 | cli-attribution-gap | reasons/not-invoked-rtk.json |
| sandbox-runtime | runtime/service/CI consumer | unknown | 0.0.79 | unverified/not this client | other-consumer | reasons/not-invoked-sandbox-runtime.json |
| serena | Codex MCP registration | 130 | 2.0.0.dev0 | 2.0.0.dev0 | invoke | receipts/invoke-serena.json |
| skfolio | runtime/service/CI consumer | unknown | 1.7.0 | unverified/not this client | other-consumer | reasons/not-invoked-skfolio.json |
| socraticode | Codex MCP registration | 64 | 1.15.0 | 1.16.0 | invoke-pending-registration | receipts/invoke-socraticode.json |
| syft | Codex shell/CLI role | unknown | 1.54.0 | 1.54.1 | cli-attribution-gap | reasons/not-invoked-syft.json |
| systemd | Codex shell/CLI role | unknown | 255.4-1ubuntu8.17 | 259.5-0ubuntu3.4 | cli-attribution-gap | reasons/not-invoked-systemd.json |
| tavily-cli | Codex shell/CLI role | unknown | 0.1.8 | unverified/not this client | cli-attribution-gap | reasons/not-invoked-tavily-cli.json |
| vllm | runtime/service/CI consumer | unknown | 0.30.0 | unverified/not this client | other-consumer | reasons/not-invoked-vllm.json |
| worktrunk | Codex shell/CLI role | unknown | 0.80.0 | 0.80.0 | cli-attribution-gap | reasons/not-invoked-worktrunk.json |
| zizmor | Codex shell/CLI role | unknown | 1.30.1 | 1.30.1 | cli-attribution-gap | reasons/not-invoked-zizmor.json |
