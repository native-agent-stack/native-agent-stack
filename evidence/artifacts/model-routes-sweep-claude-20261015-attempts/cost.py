import json, sys
# Opus 5.5 list prices per MTok (claude-api skill shared/models.md:79, prompt-caching.md:144): input $4, output $20, cache read $0.20; cache writes at the 1-hour rate (2x input = $8) as an upper estimate.
P = {"input_tokens": 4.0, "output_tokens": 20.0, "cache_read_input_tokens": 0.20, "cache_creation_input_tokens": 8.0}
tot = 0.0
for path in sys.argv[1:]:
    d = json.load(open(path))
    cu = d["child_usage"]
    for ch in cu["children"]:
        u = ch["usage"]
        c = sum(u.get(k, 0) / 1e6 * v for k, v in P.items())
        tot += c
        print(f"{ch['label']:34s} status_complete={ch.get('complete')} efforts={ch.get('efforts')} web={ch.get('web_search',{}).get('calls')} capped={ch.get('web_search',{}).get('capped')} ~${c:.2f}")
    print(path.split('/')[-1], "status", cu["status"])
print(f"CUMULATIVE ~${tot:.2f} (list-price upper estimate, advisor calls not counted)")
