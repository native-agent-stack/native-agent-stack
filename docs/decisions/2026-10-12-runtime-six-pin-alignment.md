# Runtime pin alignment to the measured host (2026-10-12)

The six current runtime pins now match versions already observed on the Linux host. This is a bounded pin and artifact-identity reconciliation. The dated catalog winner comparisons, macOS pins, Python Codex SDK/worker pin, and older lifecycle/model receipts retain their recorded scope.

| Component | Previous current pin | Measured pin | Primary release/source | Host check |
| --- | --- | --- | --- | --- |
| SocratiCode | 1.15.0 | 1.16.0 | [v1.16.0](https://github.com/giancarloerra/SocratiCode/releases/tag/v1.16.0), source 3d3a4a4d427cb0f29de4f5dd1360da52896f62df | Installed plugin and package metadata both 1.16.0; no MCP server startup |
| ai-memory | 2.4.1 | 2.6.3 | [v2.6.3](https://github.com/akitaonrails/ai-memory/releases/tag/v2.6.3), source 385b81ea95f7b73ede7146d0ae606c4caa7b43c1 | ai-memory --version; installed binary matches the verified release archive |
| Dagu | 2.16.6 | 2.18.2 | [v2.18.2](https://github.com/dagucloud/dagu/releases/tag/v2.18.2), source 5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4 | dagu version; installed binary matches the verified release archive |
| Promptfoo | 0.123.1 | 0.124.0 | [0.124.0](https://github.com/promptfoo/promptfoo/releases/tag/0.124.0), source 30949931ee90c963acd487e97828c9441db0bcd4 | promptfoo --version |
| Codex CLI | 0.160.0 | 0.162.1 | [rust-v0.162.1](https://github.com/openai/codex/releases/tag/rust-v0.162.1), source 092d3acd6bec3e3a14bdc7e7a2810ab628ab759d | codex --version; wrapper/platform registry archives verified |
| systemd | 255.4-1ubuntu8.17 | 259.5-0ubuntu3.4 | [259 release notes](https://github.com/systemd/systemd/releases/tag/v259), [v259.5 point release](https://github.com/systemd/systemd/releases/tag/v259.5), source b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a | systemctl --version, dpkg-query and the user manager's Version property agree |

SocratiCode 1.16 adds opt-in Git-triggered index refresh and startup/deletion fixes. Codex 0.162.1 fixes asynchronous-question rendering and background-server compatibility checks. Promptfoo 0.124.0 removes hosted ChatKit and moves several provider SDKs to explicit/optional installs. These release notes explain the selected versions; they do not establish execution of those mechanisms on this host.

The vendor artifacts were downloaded and independently hashed. npm archives match their registry SHA512/SHA1; ai-memory and Dagu archives match published SHA256 release digests. The Linux Codex pin retains the existing bootstrap's strict wrapper/platform-alias/version/executable checks and the complete platform tree, with its new measured hashes. No installer or lifecycle script was run for this alignment.

The [qualification receipt](../../evidence/receipts/runtime-six-pin-alignment-20261012.json) records each primary source and host check. The [versioned install-plan overlay](../../evidence/artifacts/runtime-six-pin-alignment-20261012/install-plan.json) records supported vendor routes and explicitly supersedes only the older Promptfoo runtime-version target. The complete October 2 clean-install plan remains a dated reproducible record; comparison arms and destination acceptance remain unprovisioned until their own conditions are met.

The systemd pin is the installed Ubuntu package/user-manager version, with the upstream 259/259.5 release lineage. The assignment changes no system unit, property, package, memory store, client setting, credential or trading resource.

Layer-resolution inputs were read before this delta: foundation verdicts for native-clients, agent-sdks, durable-memory, semantic-rag, quality-evaluation and scheduling-supervision; the retained 20260922 verdict wave; and the latest covering 20260929 sweep manifest/returns. Existing survivor sets and recorded verdict pins are preserved. Source and version checks do not settle the outstanding layer comparisons or promote a layer to FINAL.

Inventory provenance: the CC's measured INVENTORY.json used here hashes to 28416fe8891b23964e77ea591a5d1cad871b748c5ab08d2b7e98e2afea459d48, README.md to 4d8a23ec6e037e5f7886ba798df3cc88e9fff09e2403ca0658175cfdf4ce9d80. Its committed source base is 429f0421; collection ran at d8f7e205, and the record disclosed the pending rebuild. The six host version checks were independently repeated for this alignment.
