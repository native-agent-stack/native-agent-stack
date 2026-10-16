"""Deterministic document screen; run with python3 -I, never cloned code.

All source documents are untrusted data. Outputs are printed as native
apply_patch payloads; this program never writes files or changes configuration.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]  # this checkout (tools/landscape/screen_generic.py); a caller may reassign it
BASE = None  # caller-set Path: one <owner>__<repo> clone per list, each checked out at its pin (extract, external_resources)
OUT = None  # caller-set Path: run() reads OUT/'native-survivor-review.json'; artifacts() names its outputs under OUT
GAP = None  # caller-set Path: run() reads the gap file's updated_utc
BOARD = None  # caller-set Path: definitions() reads the readiness board's 'slots' list
AMEND = REFERENCE = None  # caller-set Paths: run() records the S4 amendment and the reference implementation it names
REPOS = [
    'abhisheknaiidu/awesome-github-profile-readme', 'alebcay/awesome-shell',
    'avelino/awesome-go', 'awesome-foss/awesome-sysadmin',
    'awesome-selfhosted/awesome-selfhosted', 'docker/awesome-compose',
    'enaqx/awesome-react', 'f/prompts.chat', 'fffaraz/awesome-cpp',
    'jaywcjlove/awesome-mac', 'sindresorhus/awesome',
    'sindresorhus/awesome-nodejs', 'veggiemonk/awesome-docker',
    'vinta/awesome-python',
]
# The keys are the committed layer fields, not a list limited to open gaps.
TERMS = {
    'native-clients': r'\b(?:codex|claude[ -]code|coding[ -](?:agent|assistant)|code[ -]assistant|aider|goose|open[ -]?code|gemini[ -]cli|native[ -]client)\b',
    'instructions-skills': r'\b(?:agent[ -]skills?|skill\.md|claude[ -](?:skills?|plugins?)|codex[ -](?:skills?|plugins?)|system[ -]prompts?|prompt[ -](?:engineer|library|manager|collection)|coding[ -]guidelines|agents\.md|claude\.md)\b|提示词|提示詞',
    'workers': r'\b(?:multi[ -]agents?|subagents?|agent[ -](?:teams?|workers?|delegat)|task[ -](?:ownership|tracking)|beads|agent[ -]orchestrat|worktrees?)\b',
    'isolation': r'\b(?:sandbox(?:ing)?|worktrees?|container[ -](?:runtime|isolat)|podman|docker|virtual[ -]machines?|virtualization|virtualisation|firejail|bubblewrap|nsjail)\b|沙盒|虚拟机|虛擬機',
    'code-navigation': r'\b(?:code[ -](?:search|navigation|index|graph)|source[ -](?:search|navigation)|symbol[ -](?:search|retriev)|ast[ -]grep|tree[ -]sitter|language[ -]server|semantic[ -](?:code|search)|ripgrep|ctags|serena|codebase[ -]memory|jcodemunch)\b',
    'document-retrieval': r'\b(?:document[ -](?:search|retriev|pars|ingest|convert)|full[ -]text[ -]search|pdf|ocr|markdown[ -](?:search|convert)|qmd|markitdown|poppler|mineru|documentation[ -](?:search|browser))\b|全文搜索|文档检索|文檔檢索',
    'semantic-rag': r'\b(?:retrieval[ -]augmented|rag|vector[ -](?:database|search|store)|embedding(?:s)?|semantic[ -](?:retriev|search)|qdrant|faiss|chroma|milvus|weaviate|llamaindex|llama[ -]index)\b',
    'durable-memory': r'\b(?:agent[ -]memory|persistent[ -]memory|durable[ -]memory|long[ -]term[ -]memory|cross[ -](?:session|client)[ -](?:memory|handoff)|ai[ -]memory|hindsight|mem0|memorag)\b',
    'web-research': r'\b(?:web[ -](?:search|scrap|crawl|research)|browser[ -](?:automation|testing|agent)|playwright|puppeteer|selenium|tavily|research[ -]agent|literature[ -](?:search|review)|arxiv|scholar|citations?)\b|网页抓取|網頁抓取|网络爬虫|網絡爬蟲',
    'token-efficiency': r'\b(?:context[ -](?:window|compress|management|optimization)|token[ -](?:cost|usage|efficien|optim|compress|saving)|prompt[ -]compress|repomix|headroom|toon|ccusage|rtk|context[ -]mode)\b',
    'quality-evaluation': r'\b(?:test(?:ing|s|er)?|tdd|bdd|pytest|unittest|property[ -]based|fuzz(?:ing|er)?|lint(?:ing|er)?|static[ -](?:analysis|analyz|analyser)|code[ -](?:review|quality|analysis)|eval(?:uation|s)?|benchmark(?:ing)?|debug(?:ging|ger)?|shellcheck|mcp[ -]inspector)\b|测试|測試|调试|調試|代码质量|代碼質量',
    'ci-supply-chain': r'\b(?:continuous[ -](?:integration|delivery)|ci/cd|github[ -]actions|dependabot|dependencies|dependency[ -](?:audit|scan|management)|supply[ -]chain|sbom|attestations?|actionlint|zizmor|gitleaks|syft|trivy|grype|sast|semgrep|codeql|vulnerabilit|security[ -](?:scan|audit))\b',
    'scheduling-supervision': r'\b(?:schedul(?:er|ing|ed)|cron|workflow[ -](?:engine|automation|management)|task[ -](?:queue|runner|scheduler)|job[ -](?:queue|runner|scheduler)|process[ -](?:supervis|management)|dagu|temporal|systemd|n8n|airflow|prefect|luigi|celery|huey|rq)\b|任务调度|任務調度',
    'hosting-services': r'\b(?:web[ -](?:framework|server)|api[ -](?:framework|server)|application[ -]server|reverse[ -]proxy|load[ -]balanc|docker|containers?|compose|podman|kubernetes|postgres(?:ql)?|next\.?js|react|fastapi|asgi|wsgi|nginx|caddy|traefik|fastify|express)\b|反向代理|网页框架|網頁框架',
    'recovery-portability': r'\b(?:backup|restore|recovery|replicat|restic|borg|duplicati|rclone|package[ -](?:manager|management)|environment[ -]management|version[ -]manager|uv|mise|asdf|nix|portable[ -](?:environment|session))\b|备份|備份|恢复|恢復',
    'observation-inference': r'\b(?:observability|monitor(?:ing)?|metrics?|telemetry|trac(?:ing|es)|logs?|logg(?:ing|er)|prometheus|grafana|loki|opentelemetry|otel|alertmanager|ntfy|vllm|inference|llama\.cpp|llama-cpp)\b|监控|監控|日志|日誌',
    'agent-sdks': r'\b(?:agent[ -](?:sdk|framework|runtime)|agents[ -]sdk|openhands|langgraph|autogen|crewai|smolagents|pydantic[ -]ai|llm[ -](?:framework|application)|coding[ -]agent|ai[ -]agents?)\b',
    'mcp-surfaces': r'\b(?:mcp|model[ -]context[ -]protocol|mcporter)\b',
    'secrets-credentials': r'\b(?:secrets?|credentials?|password[ -]manager|vault|openbao|keychain|keyring|gitleaks|sops|age[ -]encrypt|pass(?:word)?[ -]storage)\b|密码管理|密碼管理',
    'git-github-automation': r'\b(?:git|github|worktree|pull[ -]request|merge[ -]request|structural[ -]diff|difftastic|git[ -]diff|lazygit|gitui)\b',
    'market-data-reference': r'\b(?:market[ -]data|stock[ -](?:data|market|prices?)|equities|equity[ -]data|sec[ -]filings?|edgar|alpaca|ibkr|interactive[ -]brokers|corporate[ -]actions|trading[ -]calendar|financial[ -]data|yahoo[ -]finance|yfinance)\b',
    'identity-provenance': r'\b(?:data[ -](?:lineage|provenance|versioning)|dvc|lakefs|cik|corporate[ -]actions|ticker[ -](?:mapping|history)|survivorship|delisting|as[ -]known|point[ -]in[ -]time)\b',
    'storage-compute': r'\b(?:database|sql|parquet|arrow|duckdb|dataframe|pandas|polars|data[ -](?:processing|analysis|warehouse|lake)|query[ -]engine|scientific[ -]comput|numpy|dask|ray)\b|数据库|資料庫|數據庫|数据分析|數據分析',
    'data-quality-orchestration': r'\b(?:data[ -](?:quality|validation|pipeline|orchestrat)|pandera|great[ -]expectations|dagster|etl|elt|workflow[ -](?:engine|automation)|airflow|prefect)\b',
    'research-factors-ml': r'\b(?:factor[ -](?:research|model|invest)|quantitative[ -](?:finance|research|trading)|financial[ -](?:machine[ -]learning|research)|skfolio|alphalens|zipline|backtrad(?:er|ing)|portfolio[ -]optim|financial[ -]model)\b',
    'backtesting-engine': r'\b(?:backtest(?:ing|er)?|nautilus[ _-]?trader|quantconnect|zipline|backtrader|backtesting\.py|vectorbt|lean[ -](?:engine|trading))\b',
    'execution-broker': r'\b(?:broker[ -](?:api|adapter|execution)|alpaca|ibkr|interactive[ -]brokers|order[ -](?:execution|management)|trading[ -](?:api|engine))\b',
    'portfolio-risk': r'\b(?:portfolio|risk[ -](?:model|management|analytics)|skfolio|pyportfolioopt|riskfolio|quantstats|pyfolio|empyrical)\b',
    'evaluation-experiments': r'\b(?:experiment[ -](?:tracking|management|evaluation)|mlflow|optuna|hyperparameter|a/b[ -]test|walk[ -]forward|causal[ -](?:data|inference)|weights[ -]and[ -]biases)\b',
    'agents-models-workers': r'\b(?:research[ -]agents?|research[ -]workers?|ai[ -]memory|hindsight|qmd|serena|socraticode|context[ -]mode|llm[ -](?:agents?|orchestrat))\b',
    'observability-hosting': r'\b(?:opentelemetry|prometheus|grafana|loki|otel|observability|systemd|dagu|restic|research[ -]workflow)\b',
    'security-supply-chain': r'\b(?:supply[ -]chain|sbom|attestat|security[ -](?:scan|audit|analysis)|codeql|semgrep|sast|gitleaks|zizmor|syft|sandbox(?:ing)?)\b',
}
ALIASES = {
    'foundation-memory': ['durable-memory', 'code-navigation', 'document-retrieval', 'semantic-rag', 'token-efficiency'],
    'agents-operations': ['workers', 'scheduling-supervision', 'observation-inference', 'isolation', 'recovery-portability'],
    'data-research': ['market-data-reference', 'identity-provenance', 'storage-compute'],
    'engines-strategies': ['research-factors-ml', 'backtesting-engine', 'execution-broker', 'portfolio-risk'],
}
LIFECYCLE = {
    'skills-research': r'\b(?:research|literature|citations?|documentation[ -]search)\b',
    'skills-skill-lifecycle': r'\b(?:agent[ -]skills?|skill\.md|skill[ -](?:creat|audit|eval|verif|lifecycle))\b',
    'skills-design-intake': r'\b(?:requirements?[ -](?:analysis|gathering)|design[ -](?:intake|review)|brainstorming|product[ -]requirements?)\b',
    'skills-architecture': r'\b(?:software[ -](?:architecture|design)|codebase[ -](?:design|architecture)|refactor(?:ing)?)\b',
    'skills-implement': r'\b(?:python|uv|ruff|frontend|react|css|web[ -]framework)\b',
    'skills-test': r'\b(?:test(?:s|ing)?|tdd|property[ -]based|fuzz(?:ing)?)\b',
    'skills-debug': r'\b(?:debug(?:ging|ger)?|profil(?:ing|er))\b',
    'skills-review': r'\b(?:code[ -]review|pull[ -]request|variant[ -]analysis|static[ -]analysis)\b',
    'skills-security': r'\b(?:security|vulnerabilit|sast|codeql|semgrep|sarif|supply[ -]chain|sbom)\b',
    'skills-ci-pr': r'\b(?:github[ -]actions|continuous[ -]integration|ci/cd|pull[ -]request|git[ -]worktree)\b',
    'skills-agent-docs': r'\b(?:agents\.md|claude\.md|agent[ -]instructions?)\b',
    'skills-browser': r'\b(?:browser[ -](?:automation|testing)|playwright|puppeteer|selenium)\b',
    'skills-mcp-build': r'\b(?:mcp|model[ -]context[ -]protocol)\b',
}
ADMIN = re.compile(r'(?:^|/)(?:CONTRIBUTING|CODE_OF_CONDUCT|SECURITY|AGENTS|CLAUDE|LICENSE|SPONSORS|SUPPORT|PRIVACY|TERMS|GOVERNANCE|PULL_REQUEST_TEMPLATE)(?:[._-]|$)', re.I)
NONREPO = {'topics','sponsors','orgs','features','settings','login','search','users','marketplace','collections','events','about','site','apps','explore','pricing'}
STRONG = re.compile(r'\b(?:codex|claude[ -]code|mcp|agent[ -](?:sdk|framework)|multi[ -]agent|sandbox|backtest|stock[ -]market|quantitative[ -]finance|market[ -]data|portfolio[ -]optim)\b', re.I)
DOMAIN = re.compile(r'\b(?:games?|gaming|minecraft|spotify|youtube|tiktok|instagram|facebook|pinterest|dating|cooking|recipes|healthcare|medical|patient|music|photos?|photo[ -]gallery|ebooks?|e-books|media[ -](?:server|stream)|personal[ -]finance|cryptocurrency|bitcoin|ethereum|nft|forex|wordpress|cms|ecommerce|e-commerce|chat[ -]server|email[ -](?:client|server)|email[ -]marketing)\b', re.I)

def git(path, *args):
    return subprocess.run(['git','-C',str(path),*args], check=True, capture_output=True).stdout.decode('utf8',errors='replace').strip()

def load(path):
    return json.loads(path.read_text())

def repo_from(target):
    p = urlsplit(unquote(target).strip('<> '))
    if p.hostname not in ('github.com','www.github.com','raw.githubusercontent.com'):
        return None
    parts = p.path.strip('/').split('/')
    if len(parts)<2 or parts[0].lower() in NONREPO:
        return None
    repo = parts[0]+'/'+re.sub(r'\.git$','',parts[1]).rstrip('.,;:')
    return repo if re.fullmatch(r'[\w.-]+/[\w.-]+',repo) else None

def one_line(value):
    return re.sub(r'\s+',' ',str(value)).strip()

def text(path):
    if path.is_symlink():
        return ''
    return path.read_bytes().decode('utf8',errors='replace')

def definitions():
    fields = {}
    for name in ('foundation.json','us-equities.json'):
        path=ROOT/'catalogs/landscape'/name
        body=path.read_text()
        obj=json.loads(body)
        for row in obj['layers']+obj.get('domain_rows',[]):
            line=body[:body.find('"layer_id": "'+row['layer_id']+'"')].count('\n')+1
            fields[row['layer_id']]={
                'title':row['title'],'requirement':row['requirement'],
                'incumbent':row['current_choice'],'catalog_path':str(path.relative_to(ROOT)),
                'catalog_line':line,
                'catalog_citation':f'native-agent-stack@{git(ROOT,"rev-parse","HEAD")}:{path.relative_to(ROOT)}:{line}',
            }
    lifecycle=load(ROOT/'catalogs/landscape/skills-lifecycle.json')['tasks']
    components=load(ROOT/'manifests/stack.json')['components']
    selected=collections.defaultdict(list)
    for row in components:
        r=repo_from(row['repository'])
        if r:
            selected[r.lower()].append({'id':row['id'],'source':'manifests/stack.json','role':row['role'],'selected_source_pin':row.get('source_pin')})
    for name,key in [('adoption/skills/manifest.json','skills'),('blueprints/runtime-workers/skills/manifest.json','skills')]:
        for row in load(ROOT/name)[key]:
            r=repo_from(row.get('url','')) or row.get('source')
            if r and re.fullmatch(r'[\w.-]+/[\w.-]+',r):
                selected[r.lower()].append({'id':row['name'],'source':name,'status':row.get('status')})
    board=load(BOARD)
    slots=[{'index':i,'slot':row['slot']} for i,row in enumerate(board['slots'])]
    return fields,lifecycle,components,selected,slots

def document_files(files):
    return [f for f in files if re.search(r'\.(?:md|mdx|rst)$',f,re.I) and not ADMIN.search(f) and not re.search(r'(?:^|/)(?:node_modules|wwwroot/lib)/',f)]

def screen(row, selected, slots):
    # An occurrence's own descriptive line plus the closest section heading.
    # Repository identity tokens alone do not make a GitHub link relevant.
    descriptive=re.sub(r'https?://[^\s<>"\x27)\]]+',' ',row['description'])
    hay=one_line(row['title']+' '+descriptive+' '+row['section'])
    layer_matches={k:re.search(v,hay,re.I) for k,v in TERMS.items()}
    layers=[k for k,m in layer_matches.items() if m]
    lifecycle=[k for k,v in LIFECYCLE.items() if re.search(v,hay,re.I)]
    # Every React library is not an additional Python skill. Lifecycle matches
    # are retained separately and never alone promote an ecosystem component.
    aliases=[k for k,vs in ALIASES.items() if any(v in layers for v in vs)]
    incumbent=selected.get(row['repository'].lower(),[])
    board_matches=[]
    label_tokens=set(re.findall(r'[a-z0-9]+',hay.lower()))
    for slot in slots:
        name=slot['slot'] if isinstance(slot['slot'],str) else json.dumps(slot['slot'])
        token=name.split(' ')[0].split(':')[-1].lower().strip('[]()')
        if len(token)>3 and token in label_tokens:
            board_matches.append(slot['index'])
    row.update(layer_ids=layers,domain_aliases=aliases,lifecycle_fields=lifecycle,
               readiness_slots=board_matches,incumbent_ids=sorted({x['id'] for x in incumbent}))
    if row['kind']=='administrative-reference':
        row.update(disposition='OUT-OF-SCOPE',reason='Administrative-only GitHub reference is noncandidate provenance; searched target URL, own occurrence line and section. It does not establish a runtime nominee or support repository-level rejection.')
    elif row['kind']=='prompt-embedded-reference':
        row.update(disposition='OUT-OF-SCOPE',reason='Noncandidate GitHub URL embedded in a user-contributed prompt body, not a registry assertion of target repository capability; searched prompt line/title and surrounding prompt section against all 32 layer patterns. This reference cannot support a runtime-repository verdict; target suitability UNVERIFIED.')
    elif row['source_repository']=='abhisheknaiidu/awesome-github-profile-readme' and not STRONG.search(hay) and not incumbent:
        row.update(disposition='OUT-OF-SCOPE',reason='Profile README/showcase entry; source line is a personal profile or decorative profile generator, not a native engineering capability.')
    elif not layers and not incumbent:
        row.update(disposition='OUT-OF-SCOPE',reason='No committed layer capability matched; searched this source line/title and closest section against all 32 layer regexes and 13 lifecycle aliases recorded in field-screen.json.')
    elif DOMAIN.search(hay) and not STRONG.search(hay) and not incumbent:
        row.update(disposition='OUT-OF-SCOPE',reason='Domain-specific application/library outside the current native engineering and US-equities scope; screened all matched layer keywords and the explicit domain terms in screen_generic.py.')
    elif row['kind']=='github-reference' and (row['source_repository']=='sindresorhus/awesome' or re.search(r'(?:^|/)awesome(?:[-_]|$)|^awesome[-_]',row['repository'],re.I)):
        row.update(disposition='NO-GAP',reason='Discovery-list/reference pointer; no runtime nominee or measured capability gap is established at this reference. Searched own occurrence line, title and section; recursive mining beyond the assigned 14 lists remains UNVERIFIED. This is discovery provenance, not a rejected runtime.')
    elif incumbent:
        row.update(disposition='NO-GAP',reason='Repository identity occurs in the committed selected component/skill manifest; this occurrence adds no measured capability. Current-pin behavior, deployment and both-client acceptance remain UNVERIFIED in this generic screen.')
    else:
        row.update(disposition='WATCH',reason='Relevant capability asserted by a current-month-fetched source-list document; native fit, candidate pin, supported vendor install/check/inverse, cross-client routing and comparative benefit are UNVERIFIED. No adoption or trial is authorized by this document screen.')
    row['verification']='MEASURED source document extraction; list capability assertion and runtime suitability UNVERIFIED'
    row['searched']='source occurrence title/line, closest section, all committed 32 layer terms, four domain aliases, 13 lifecycle aliases, selected manifest repository identities; no cloned code executed'
    row['layer_match_evidence']={k:hay[max(0,m.start()-60):m.end()+80] for k,m in layer_matches.items() if m}
    row['description_characters']=len(row['description'])
    row['description_sha256']=hashlib.sha256(row['description'].encode()).hexdigest()
    row['description']=row['description'][:1400]
    return row

def extract(repo, selected, slots):
    directory=BASE/repo.replace('/','__')
    pin=git(directory,'rev-parse','HEAD')
    files=git(directory,'ls-files','-z').split('\0')
    files=[f for f in files if f]
    docs=document_files(files)
    rows=[]
    inventories=[]
    def add(file,line,title,target,desc,section,kind='github-reference'):
        target=target.strip('<> ').rstrip('.,;')
        candidate=repo_from(target)
        if kind in ('prompt','compose-recipe','native-plugin'):
            candidate=repo
        if not candidate:
            return
        if re.search(r'/issues(?:/|$)|/pull(?:s|/|$)|/actions(?:/|$)|/graphs(?:/|$)|/discussions(?:/|$)|/wiki(?:/|$)|/releases(?:/|$)|/compare(?:/|$)|/contributors(?:/|$)|/stargazers(?:/|$)|/blob/[^/]+/(?:LICENSE|CONTRIBUTING)',target,re.I):
            kind='administrative-reference'
        row={'source_repository':repo,'source_pin':pin,'path':file,'line':line,'citation':f'{repo}@{pin}:{file}:{line}',
             'title':one_line(title),'target':target,'repository':candidate,'description':one_line(desc),'section':one_line(section),'kind':kind}
        rows.append(screen(row,selected,slots))
    for file in docs:
        body=text(directory/file)
        inventories.append({'path':file,'sha256':hashlib.sha256(body.encode()).hexdigest(),'lines':len(body.splitlines()),'github_occurrences':0})
        headings=[]
        refs={}
        for n,line in enumerate(body.splitlines(),1):
            m=re.match(r'^\s*\[([^]]+)\]:\s*(\S+)',line)
            if m:refs[m[1].lower()]=m[2]
        for n,line in enumerate(body.splitlines(),1):
            heading=re.match(r'^(#{1,6})\s+(.+)',line)
            if heading:
                depth=len(heading[1]);headings=headings[:depth-1]+[heading[2]]
            section=' / '.join(headings[-2:])
            matches=[]
            for m in re.finditer(r'(?<!!)\[([^\]\n]*)\]\((<?[^\s)]+>?)',line):
                matches.append((m[1],m[2],m.start(2)))
            for m in re.finditer(r'<a\b[^>]*href=["\x27]([^"\x27]+)["\x27][^>]*>(.*?)</a>',line,re.I):
                matches.append((re.sub(r'<[^>]+>','',m[2]),m[1],m.start(1)))
            for m in re.finditer(r'(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]',line):
                target=refs.get((m[2] or m[1]).lower())
                if target:matches.append((m[1],target,m.start()))
            used_positions={pos for _,_,pos in matches}
            for m in re.finditer(r'https?://(?:www\.)?(?:github\.com|raw\.githubusercontent\.com)/[^\s<>"\x27)\]]+',line,re.I):
                if m.start() not in used_positions:matches.append(('',m[0],m.start()))
            for title,target,_ in matches:
                before=len(rows)
                if repo_from(target):
                    kind='prompt-embedded-reference' if repo=='f/prompts.chat' and (file=='PROMPTS.md' or file.startswith('prompts/')) else 'github-reference'
                    add(file,n,title or repo_from(target),target,line,section,kind)
                elif repo=='docker/awesome-compose' and file=='README.md' and not urlsplit(target).scheme and not target.startswith('#'):
                    add(file,n,title,target,line,section,'compose-recipe')
                if len(rows)>before:inventories[-1]['github_occurrences']+=1
    if repo=='f/prompts.chat':
        file='prompts.csv'
        if file in files:
            body=text(directory/file)
            reader=csv.DictReader(io.StringIO(body))
            start=2
            for rec in reader:
                title=rec.get('act') or rec.get('title') or rec.get('name') or ''
                desc=rec.get('prompt') or rec.get('content') or ''
                add(file,start,title,'https://github.com/'+repo+'/blob/'+pin+'/'+file,desc,'Prompt catalog','prompt')
                start=reader.line_num+1
            inventories.append({'path':file,'sha256':hashlib.sha256(body.encode()).hexdigest(),'lines':len(body.splitlines()),'kind':'prompt-csv','records':reader.line_num})
        for file in files:
            if file.endswith(('.claude-plugin/plugin.json','.claude-plugin/marketplace.json')):
                body=text(directory/file)
                try:obj=json.loads(body)
                except json.JSONDecodeError:continue
                title=obj.get('name','prompts.chat')
                add(file,1,title,'https://github.com/'+repo+'/blob/'+pin+'/'+file,json.dumps(obj,ensure_ascii=False),'Native Claude plugin manifest','native-plugin')
                inventories.append({'path':file,'sha256':hashlib.sha256(body.encode()).hexdigest(),'lines':len(body.splitlines()),'kind':'native-plugin-manifest'})
    for n,row in enumerate(rows,1):row['entry_id']=repo.replace('/','__')+f':{n:06d}'
    summary={'repository':repo,'pin':pin,'commit_date':git(directory,'show','-s','--format=%cI'),
             'retrieved_utc':git(directory,'reflog','-1','--date=iso-strict','--format=%gd'),
             'inspected_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'shallow':git(directory,'rev-parse','--is-shallow-repository'),
             'tracked_files':len(files),'inventory_files':inventories,'document_files_scanned':len(docs),
             'entries_extracted':len(rows),'entries_dispositioned':len(rows),
             'relevant_entries':sum(bool(r['layer_ids'] or r['incumbent_ids']) and r['disposition']!='OUT-OF-SCOPE' for r in rows),
             'unique_repository_links':len({r['repository'].lower() for r in rows}),
             'counts_by_disposition':dict(collections.Counter(r['disposition'] for r in rows)),
             'counts_by_kind':dict(collections.Counter(r['kind'] for r in rows)),
             'excluded_files':{'administrative_markdown':[f for f in files if re.search(r'\.(?:md|mdx|rst)$',f,re.I) and ADMIN.search(f)],
                               'non_inventory_tracked_files':len(files)-len(docs)}}
    return summary,rows

def external_resources(selected,slots):
    """Inventory external tool/docs references as source-list assertions only."""
    entries=[];ignored=collections.Counter()
    noise_hosts={'img.shields.io','shields.io','badge.fury.io','badgen.net','ko-fi.com','patreon.com','opencollective.com','buymeacoffee.com'}
    for repo in REPOS:
        directory=BASE/repo.replace('/','__');pin=git(directory,'rev-parse','HEAD')
        files=document_files([f for f in git(directory,'ls-files','-z').split('\0') if f])
        count=0
        for file in files:
            body=text(directory/file);headings=[];refs={}
            for line in body.splitlines():
                m=re.match(r'^\s*\[([^]]+)\]:\s*(\S+)',line)
                if m:refs[m[1].lower()]=m[2]
            for n,line in enumerate(body.splitlines(),1):
                m=re.match(r'^(#{1,6})\s+(.+)',line)
                if m:headings=headings[:len(m[1])-1]+[m[2]]
                section=' / '.join(headings[-2:]);matches=[]
                for m in re.finditer(r'(?<!!)\[([^\]\n]*)\]\((<?[^\s)]+>?)',line):matches.append((m[1],m[2],m.start(2)))
                for m in re.finditer(r'<a\b[^>]*href=["\x27]([^"\x27]+)["\x27][^>]*>(.*?)</a>',line,re.I):matches.append((re.sub(r'<[^>]+>','',m[2]),m[1],m.start(1)))
                for m in re.finditer(r'(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]',line):
                    t=refs.get((m[2] or m[1]).lower())
                    if t:matches.append((m[1],t,m.start()))
                positions={p for _,_,p in matches}
                if re.match(r'^\s*(?:[-*]|\||\d+[.)])',line):
                    for m in re.finditer(r'https?://[^\s<>"\x27)\]]+',line):
                        if m.start() not in positions:matches.append(('',m[0],m.start()))
                for title,target,_ in matches:
                    target=target.strip('<> ').rstrip('.,;');p=urlsplit(target)
                    if p.scheme not in ('http','https'):continue
                    if p.hostname in ('github.com','www.github.com','raw.githubusercontent.com'):continue
                    if p.hostname in noise_hosts or re.search(r'\.(?:png|jpe?g|gif|webp|svg)(?:\?|$)',p.path,re.I):
                        ignored['badges-images-sponsors']+=1;continue
                    row={'source_repository':repo,'source_pin':pin,'path':file,'line':n,
                         'citation':f'{repo}@{pin}:{file}:{n}','title':one_line(title or p.hostname),
                         'target':target,'repository':'__external__/unresolved','description':one_line(line),'section':section,
                         'kind':'prompt-embedded-reference' if repo=='f/prompts.chat' and (file=='PROMPTS.md' or file.startswith('prompts/')) else 'external-tool-doc-reference'}
                    row=screen(row,selected,slots)
                    if repo=='sindresorhus/awesome' and row['disposition']=='WATCH':
                        row.update(disposition='NO-GAP',reason='Recursive awesome-list or general reference pointer; no runtime nominee or measured capability gap established at this reference. Searched external title, own description and section across all layer terms. Recursive mining and executable vendor capability remain UNVERIFIED.')
                    row['repository']=None
                    row['verification']='MEASURED external URL extraction; external upstream content/maintenance/runtime UNVERIFIED; no external fetch performed'
                    count+=1;row['entry_id']=repo.replace('/','__')+f':external:{count:06d}'
                    entries.append(row)
    return entries,dict(ignored)

def run():
    csv.field_size_limit(8_000_000)
    fields,lifecycle,components,selected,slots=definitions()
    assert set(TERMS)=={k for k in fields if k not in ALIASES}, '32 field coverage mismatch'
    summaries=[];allrows=[]
    for repo in REPOS:
        summary,rows=extract(repo,selected,slots);summaries.append(summary);allrows.extend(rows)
    groups=collections.defaultdict(list)
    for row in allrows:groups[row['repository'].lower()].append(row)
    unique=[]
    priority={'NO-GAP':0,'WATCH':1,'REJECT':2,'OUT-OF-SCOPE':3}
    for key,rows in sorted(groups.items()):
        relevant=[r for r in rows if r['disposition']!='OUT-OF-SCOPE' and (r['layer_ids'] or r['incumbent_ids'])]
        if not relevant:continue
        # A real capability entry takes precedence over its badge or list pointer.
        real=[r for r in relevant if not (r['kind']=='prompt-embedded-reference' or (r['disposition']=='NO-GAP' and not r['incumbent_ids']))]
        row=min(real or relevant,key=lambda r:priority[r['disposition']])
        unique.append({'repository':row['repository'],'disposition':row['disposition'],
                       'layer_ids':sorted({x for r in relevant for x in r['layer_ids']}),
                       'domain_aliases':sorted({x for r in relevant for x in r['domain_aliases']}),
                       'lifecycle_fields':sorted({x for r in relevant for x in r['lifecycle_fields']}),
                       'readiness_slots':sorted({x for r in relevant for x in r['readiness_slots']}),
                       'incumbent_ids':sorted({x for r in relevant for x in r['incumbent_ids']}),
                       'source_occurrences':len(rows),'relevant_occurrences':len(relevant),
                       'evidence':sorted({r['citation'] for r in relevant}),
                       'list_claim':row['description'],'reason':row['reason'],'searched':row['searched'],
                       'verification':row['verification'],'candidate_pin':None})
    review=load(OUT/'native-survivor-review.json')
    deep={r['repository'].lower():r for r in review['candidates']}
    for row in unique:
        if row['repository'].lower() in deep:
            r=deep[row['repository'].lower()]
            row['candidate_pin']=r['pin']
            row['candidate_commit_date']=r['commit_date']
            row['layer_ids']=sorted(set(row['layer_ids']+r['layer_ids']))
            row['evidence']=sorted(set(row['evidence']+r['evidence']))
            row['primary_source_finding']=r['source_finding']
            row['verification']='MEASURED source-list extraction; primary upstream source reviewed at pinned HEAD; runtime/comparison UNVERIFIED'
    counts={'lists':len(REPOS),'entries':len(allrows),'dispositioned':len(allrows),
            'relevant_occurrences':sum(s['relevant_entries'] for s in summaries),
            'all_unique_repositories':len(groups),'relevant_unique_repositories':len(unique),
            'occurrence_dispositions':dict(collections.Counter(r['disposition'] for r in allrows)),
            'relevant_unique_dispositions':dict(collections.Counter(r['disposition'] for r in unique)),
            'layer_counts':{k:sum(k in r['layer_ids'] or k in r['domain_aliases'] for r in unique) for k in fields},
            'gh_api_calls':0,'web_search_calls':0,'web_fetch_calls':0,'code_executed_from_clones':0}
    sidecars=[]
    gap=load(GAP)
    for row in unique:
        sidecars.append({'repository':row['repository'],'pin':None,'list_source_pins':sorted({r['source_pin'] for r in groups[row['repository'].lower()]}),
                         'layer_ids':row['layer_ids'],'gap_id':None,
                         'gap_status':'UNVERIFIED: this document screen does not assert an open host or design gap; stale gap-file updated_utc='+gap['updated_utc'],
                         'incumbent':{k:fields[k]['incumbent'] for k in row['layer_ids']},
                         'incumbent_component_ids':row['incumbent_ids'],
                         'install':'UNVERIFIED candidate vendor command; no installs in this lane',
                         'check':'UNVERIFIED host/runtime check; source extraction is the only measured check',
                         'inverse':'UNVERIFIED until a concrete vendor install is qualified',
                         'native_routing':{'codex':'UNVERIFIED candidate-specific routing; generic document screen only','claude':'UNVERIFIED candidate-specific routing; generic document screen only'},
                         'disposition':row['disposition'],'evidence':row['evidence'],
                         'reason':row['reason'],'searched':row['searched'],
                         'claim_boundary':'List assertion only; no API metadata, candidate clone, installed acceptance, or comparative execution performed by this generic screen.'})
        if row['repository'].lower() in deep:
            r=deep[row['repository'].lower()]
            sidecars[-1].update(pin=r['pin'],commit_date=r['commit_date'],install=r['install'],check=r['check'],inverse=r['inverse'],
                                native_routing=r['native_routing'],primary_source_finding=r['source_finding'],
                                claim_boundary='Primary source review at a live shallow clone pin; no installed acceptance or comparative execution. All nine concrete survivors remain WATCH.')
    discoveries=[]
    for layer,definition in fields.items():
        proposed=[]
        for row in unique:
            if layer not in row['layer_ids']+row['domain_aliases']:continue
            proposed.append({'repository':row['repository'],
                             'proposed_label':'keep_but_compare' if row['incumbent_ids'] else 'not_adopted',
                             'demonstrated_gap':'NONE DEMONSTRATED. '+row['reason'],
                             'comparison_that_would_overturn':'A pinned upstream source review and a preregistered same-workload comparison against the committed incumbent, with vendor commands and both-client acceptance; '+definition['requirement'],
                             'evidence':row['evidence']+[definition['catalog_citation']],
                             'upstream_now':dict.fromkeys(['latest_release','released_at','stars','pushed_at','archived','license']),
                             'source':'14 generic lists, fetched 2026-10-08; relevant entry occurrence ledger; disposition='+row['disposition']})
        discoveries.append({'layer_id':layer,'proposed':proposed,
                            'calls':{'web_search':0,'web_fetch':0,'gh_api':0},
                            'notes':'Current-month source-list screen, not a superiority claim. All 32 committed fields plus four domain aliases and 13 lifecycle aliases were searched. No runtime/install comparison, no API metadata. '+('No matching relevant GitHub entry found after those searches; absence applies only to the 14 pinned documents.' if not proposed else 'Relevant unique repository decisions are in relevant-repositories.jsonl; source-list claims remain UNVERIFIED.'),
                            'skills_used':['context-mode:context-mode']})
    methodology={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_base':git(ROOT,'rev-parse','HEAD'),
                 'scope':'14 assigned generic list clones; all selected Markdown/MDX/RST including translations; prompts.csv, native Claude plugin manifests and Docker Compose local recipe links supplement GitHub links',
                 'fields':fields,'layer_regexes':TERMS,'domain_aliases':ALIASES,'lifecycle_regexes':LIFECYCLE,
                 'selected_component_aliases':[{'id':r['id'],'repository':r['repository'],'role':r['role']} for r in components],
                 'readiness_board':{'path':str(BOARD),'sha256':hashlib.sha256(BOARD.read_bytes()).hexdigest(),'slots':slots,'zero_based':True,
                                    'authority_limit':'Slot labels only; board status is historical where later S4 amendments supersede it.'},
                 'fresh_s4_amendment':{'path':str(AMEND),'sha256':hashlib.sha256(AMEND.read_bytes()).hexdigest(),
                                       'limit':'Path/hash captured; generic screen does not determine S4 readiness. Gap-depth sibling owns adjudication.'},
                 'gaps':{'path':str(GAP),'sha256':hashlib.sha256(GAP.read_bytes()).hexdigest(),'updated_utc':gap['updated_utc'],
                         'limit':'Historical lead only; no entry is excluded merely because no open gap is known.'},
                 'search_unit':'Each own occurrence line/title plus closest two Markdown headings; regex matches retained by layer; identities compared case-insensitively against selected manifests; translation occurrences retained.',
                 'deduplication':'Occurrence ledger keeps every emitted reference/prompt/recipe. Binding ledger groups case-insensitive owner/repo identities and retains every relevant source citation. Canonical repository redirects are UNVERIFIED without API.',
                 'exclusions':'Administrative Markdown and vendored browser library docs excluded; source-code/package-lock dependencies outside the repository-link inventory. External HTTP tool/docs references are retained in external-occurrences.jsonl; badges/images/sponsors are counted as ignored and external upstream content remains UNVERIFIED. Relative Compose recipe links and local prompt/plugin records retained. Relevant discovery-only list pointers receive NO-GAP; administrative, prompt-embedded and unrelated references receive OUT-OF-SCOPE. No runtime REJECT is inferred. See individual searched fields and per-list excluded file inventory.',
                 'disposition_policy':'NO-GAP means committed selection identity or discovery-only pointer without a runtime nominee/established capability gap, not latest runtime equivalence. WATCH means source-described relevant capability without a demonstrated comparative gap. Administrative-only and prompt-embedded references are OUT-OF-SCOPE/noncandidate and cannot determine a mixed-source repo verdict. Real capability entries take precedence over pointers. No runtime REJECT, ADOPT-NOW or TRIAL is inferred from untested documents.',
                 'untested_boundaries':['non-GitHub external resources','unlinked source-code dependencies','recursive mining of unassigned lists','candidate canonical redirect/pin/release/license','native vendor install/check/inverse','host deployment and cross-client routing','comparative performance','historical market-data eligibility and broker acceptance'],
                 'counts':counts}
    methodology['primary_source_review']={'path':str(OUT/'native-survivor-review.json'),'candidate_clones':9,'runtime_acceptance':'UNVERIFIED','candidate_pins':{r['repository']:r['pin'] for r in review['candidates']}}
    methodology['reference_implementation']={'path':str(REFERENCE),
                                             'sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
                                             'use':'Existing lane extraction implementation used as a reference; generic screen adds the full committed-field vocabulary, source-occurrence inventory and external-doc ledger. It is not a replacement for an upstream runtime feature.'}
    return summaries,allrows,unique,sidecars,discoveries,methodology

def artifacts():
    summaries,rows,unique,sidecars,discoveries,method=run()
    defs=definitions();external,ignored=external_resources(defs[3],defs[4])
    method['external_resources']={'occurrences':len(external),'relevant_occurrences':sum(bool(r['layer_ids']) and r['disposition']!='OUT-OF-SCOPE' for r in external),
                                  'unique_urls':len({r['target'] for r in external}),'dispositions':dict(collections.Counter(r['disposition'] for r in external)),
                                  'ignored':ignored,'limit':'External URLs are included in external-occurrences.jsonl, not invented as owner/repo candidate identities in discovery-records.json.'}
    method['exclusions']=method['exclusions'].replace('non-GitHub external URLs and source-code/package-lock dependencies outside the requested repository-link inventory.','source-code/package-lock dependencies outside the repository-link inventory. External HTTP tool/docs references are retained separately; badges/images/sponsors are counted as ignored.')
    out={
        'source-inventory.json':json.dumps(summaries,ensure_ascii=False,indent=2)+'\n',
        'field-screen.json':json.dumps(method,ensure_ascii=False,indent=2)+'\n',
        'relevant-repositories.jsonl':''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in unique),
        'sidecar.json':json.dumps(sidecars,ensure_ascii=False,indent=2)+'\n',
        'discovery-records.json':json.dumps(discoveries,ensure_ascii=False,indent=2)+'\n',
        'external-occurrences.jsonl':''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in external),
    }
    columns=['entry_id','source_repository','source_pin','path','line','repository','kind','title','section','layer_ids','domain_aliases','lifecycle_fields','readiness_slots','incumbent_ids','disposition','target','description','description_characters','description_sha256','layer_match_evidence','reason','searched','verification']
    for repo in REPOS:
        buf=io.StringIO();writer=csv.writer(buf,delimiter='\t',lineterminator='\n');writer.writerow(columns)
        for row in rows:
            if row['source_repository']==repo:
                writer.writerow([json.dumps(row[c],ensure_ascii=False,separators=(',',':')) if isinstance(row[c],(list,dict)) else one_line(row[c]) for c in columns])
        out['occurrences/'+repo.replace('/','__')+'.tsv']=buf.getvalue()
    return out,method['counts']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['summary','leads','artifact','patch','stream'],default='summary');parser.add_argument('--artifact');parser.add_argument('--offset',type=int,default=0);parser.add_argument('--limit',type=int,default=100);parser.add_argument('--chunk-bytes',type=int,default=60_000);parser.add_argument('--resume',action='store_true');parser.add_argument('--skip-artifacts',default='');args=parser.parse_args()
    if args.mode in ('summary','leads'):
        summaries,rows,unique,sidecars,discoveries,method=run()
        if args.mode=='summary':
            print(json.dumps({'counts':method['counts'],'source_summaries':[{k:v for k,v in s.items() if k!='inventory_files'} for s in summaries]},ensure_ascii=False))
        else:
            wanted=re.compile(r'\b(?:claude|codex|mcp|agent|memory|rag|embedding|orchestrat|observability|secret|sandbox|backup|fuzz|property|ci/cd|continuous|supply[ -]chain|market[ -]data|backtest|portfolio|edgar|alpaca)\b',re.I)
            leads=[r for r in unique if r['disposition']=='WATCH' and wanted.search(r['list_claim'])]
            print(json.dumps([{'repository':r['repository'],'layers':r['layer_ids'],'claim':r['list_claim'],'citation':r['evidence'][0]} for r in leads[args.offset:args.offset+args.limit]],ensure_ascii=False))
        return
    out,counts=artifacts()
    if args.mode=='stream':
        if not sys.stdin.isatty():
            raise SystemExit('stream requires a PTY so native apply_patch can acknowledge each bounded payload')
        print(json.dumps({'kind':'manifest','artifacts':{k:len(v.encode()) for k,v in out.items()},'counts':counts}),flush=True)
        sys.stdin.readline()
        for name,content in out.items():
            if name in args.skip_artifacts.split(','):
                continue
            lines=content.splitlines();offset=0
            if args.resume and (OUT/name).is_file():
                existing=(OUT/name).read_text()
                if not content.startswith(existing):
                    raise SystemExit('Refusing resume: existing artifact differs from regenerated prefix: '+name)
                offset=len(existing.splitlines())
            while offset<len(lines):
                end=offset;size=0
                while end<len(lines) and (size<args.chunk_bytes or end==offset):
                    size+=len(lines[end].encode())+1;end+=1
                if offset==0:
                    patch='*** Begin Patch\n*** Add File: '+str(OUT/name)+'\n'+''.join('+'+l+'\n' for l in lines[offset:end])+'*** End Patch\n'
                else:
                    patch='*** Begin Patch\n*** Update File: '+str(OUT/name)+'\n@@\n '+lines[offset-1]+'\n'+''.join('+'+l+'\n' for l in lines[offset:end])+'*** End of File\n*** End Patch\n'
                print(json.dumps({'kind':'patch','path':str(OUT/name),'offset':offset,'lines':end-offset,'total_lines':len(lines),'patch':patch},ensure_ascii=False),flush=True)
                sys.stdin.readline();offset=end
            print(json.dumps({'kind':'complete','path':str(OUT/name),'sha256':hashlib.sha256(content.encode()).hexdigest(),'bytes':len(content.encode()),'lines':len(lines)}),flush=True)
            sys.stdin.readline()
        print(json.dumps({'kind':'done','counts':counts}),flush=True);return
    if args.artifact not in out:
        print(json.dumps({'artifacts':{k:len(v.encode()) for k,v in out.items()},'counts':counts}));return
    content=out[args.artifact]
    if args.mode=='artifact':print(content,end='');return
    lines=content.splitlines();chunk=lines[args.offset:args.offset+args.limit]
    if args.offset==0:
        patch='*** Begin Patch\n*** Add File: '+str(OUT/args.artifact)+'\n'+''.join('+'+l+'\n' for l in chunk)+'*** End Patch\n'
    else:
        patch='*** Begin Patch\n*** Update File: '+str(OUT/args.artifact)+'\n@@\n '+lines[args.offset-1]+'\n'+''.join('+'+l+'\n' for l in chunk)+'*** End Patch\n'
    print(json.dumps({'patch':patch,'path':str(OUT/args.artifact),'offset':args.offset,'emitted_lines':len(chunk),'total_lines':len(lines),'counts':counts},ensure_ascii=False))

if __name__=='__main__':
    main()
