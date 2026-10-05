#!/usr/bin/env python3
"""Render an evidence-backed interview dossier. No fetching or factual inference."""
import argparse
import csv
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

LISTS = ('sources', 'overview', 'business', 'timeline', 'projects', 'policies',
         'outlook', 'interviews', 'coverage', 'clues')
FILES = ('企业面试研究手册.html', '资料数据.json', '来源目录.csv', '项目卡片.csv')


def validate(data):
    errors = []
    if not isinstance(data, dict):
        raise ValueError('JSON 顶层必须是对象')
    meta = data.get('meta')
    if not isinstance(meta, dict):
        raise ValueError('缺少 meta 对象')

    def required(obj, fields, loc):
        for key in fields:
            if not isinstance(obj.get(key), str) or not obj[key].strip():
                errors.append(f'{loc}.{key} 必须是非空字符串')

    required(meta, ('company', 'cutoff', 'period', 'scope'), 'meta')
    cutoff = meta.get('cutoff', '')
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', cutoff):
            raise ValueError()
        cutoff_date = dt.date.fromisoformat(cutoff)
    except (ValueError, TypeError):
        cutoff_date = None
        errors.append('meta.cutoff 必须是有效 YYYY-MM-DD 日期')
    limits = meta.get('limitations')
    if not isinstance(limits, list) or not all(isinstance(x, str) for x in limits):
        errors.append('meta.limitations 必须是字符串数组（可空但需真实评估）')
    for key in LISTS:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
            errors.append(f'{key} 必须是对象数组')
    if errors:
        raise ValueError('\n'.join(errors))
    if not data.get('sources'):
        errors.append('sources 不得为空')

    def id_map(key, required_fields):
        result = {}
        for i, item in enumerate(data.get(key, [])):
            loc = f'{key}[{i}]'
            required(item, required_fields, loc)
            ident = item.get('id', '')
            if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', ident):
                errors.append(f'{loc}.id 需使用字母开头的 ASCII 编号')
            elif ident in result:
                errors.append(f'{loc}.id 重复：{ident}')
            else:
                result[ident] = item
        return result

    sources = id_map('sources', ('id', 'title', 'url', 'date', 'level', 'access'))
    for sid, item in sources.items():
        try:
            parsed = urlsplit(item.get('url', ''))
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                raise ValueError()
        except (TypeError, ValueError):
            errors.append(f'{sid}.url 必须是公开 HTTP(S) URL')
        for field in ('date',):
            value = item.get(field, '')
            if cutoff_date and isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                try:
                    if dt.date.fromisoformat(value) > cutoff_date:
                        errors.append(f'{sid} 来源发布日期晚于检索截止：{value}')
                except ValueError:
                    errors.append(f'{sid}.date 日期无效')

    def refs(item, loc, field='refs', mandatory=True):
        value = item.get(field, [])
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            errors.append(f'{loc}.{field} 必须是来源ID数组')
            return
        if mandatory and not value:
            errors.append(f'{loc}.{field} 缺少来源')
        missing = [x for x in value if x not in sources]
        if missing:
            errors.append(f'{loc}.{field} 未定义来源：{missing}')

    projects = id_map('projects', ('id', 'title', 'year', 'region', 'kind', 'status', 'owner', 'fact'))
    for pid, item in projects.items():
        refs(item, pid)
        direct = item.get('policy_basis') in ('直接依据', '明确关联')
        refs(item, pid, 'policy_refs', direct)
        if 'priority' in item and not isinstance(item['priority'], bool):
            errors.append(f'{pid}.priority 必须是布尔值')
        parent = item.get('parent_id')
        if parent and (not isinstance(parent, str) or parent not in projects):
            errors.append(f'{pid}.parent_id 未定义：{parent}')
        for field in ('meaning', 'policy', 'policy_basis', 'caution'):
            if field in item and not isinstance(item[field], str):
                errors.append(f'{pid}.{field} 必须是字符串')
    for pid in projects:
        seen = set()
        current = pid
        while isinstance(current, str) and current in projects:
            if current in seen:
                errors.append(f'{pid} 存在母子项循环')
                break
            seen.add(current)
            current = projects[current].get('parent_id')

    for key in ('overview', 'business', 'policies', 'outlook', 'clues'):
        for i, item in enumerate(data.get(key, [])):
            loc = f'{key}[{i}]'
            required(item, ('title', 'text'), loc)
            refs(item, loc)
    for i, item in enumerate(data.get('timeline', [])):
        loc = f'timeline[{i}]'
        required(item, ('year', 'title', 'text'), loc)
        refs(item, loc)
    for i, item in enumerate(data.get('interviews', [])):
        loc = f'interviews[{i}]'
        required(item, ('question', 'answer'), loc)
        refs(item, loc, mandatory=False)
    for i, item in enumerate(data.get('coverage', [])):
        loc = f'coverage[{i}]'
        required(item, ('dimension', 'status', 'detail'), loc)
        if item.get('status') not in ('已覆盖', '部分覆盖', '未查得', '不适用'):
            errors.append(f'{loc}.status 不属于覆盖词汇')
        refs(item, loc, mandatory=False)
    if errors:
        raise ValueError('\n'.join(errors))
    return sources, projects


def esc(value):
    return html.escape(str(value), quote=True)


def para(value):
    return esc(value).replace('\n', '<br>')


def render(data, sources, projects):
    meta = data['meta']
    sections = []
    nav = []

    def citations(ids):
        return ' '.join(f'<a class="cite" href="{esc(sources[s]["url"])}" target="_blank" rel="noopener noreferrer" title="{esc(sources[s]["title"])}">[{esc(s)}] {esc(sources[s]["title"])}</a>' for s in ids)

    def section(key, title, content):
        nav.append(f'<a href="#{key}">{esc(title)}</a>')
        sections.append(f'<section id="{key}"><h2>{esc(title)}</h2>{content}</section>')

    def notes(items):
        return '<div class="grid">' + ''.join(f'<article><span class="badge">{esc(x.get("basis", "资料与分析"))}</span><h3>{esc(x["title"])}</h3><p>{para(x["text"])}</p>{citations(x["refs"])}</article>' for x in items) + '</div>'

    limits = ''.join(f'<li>{para(x)}</li>' for x in meta['limitations'])
    section('scope', '范围与证据', f'<p>{para(meta["scope"])}</p><p><b>主体边界：</b>{para(meta.get("entity", meta["company"]))}</p><p><b>时间窗口：</b>{esc(meta["period"])}<br><b>目标岗位：</b>{esc(meta.get("role", "未指定；通用岗位理解"))}</p><div class="callout"><b>公开资料覆盖边界</b><ul>{limits or "<li>本次未记录具体缺口；仍不据此宣称穷尽全部内部项目。</li>"}</ul><p>项目卡片含批次、子项及规划事项，数量不是独立工程总数。计划、预测、实绩与分析分别标注。</p></div>')
    for key, title in (('overview', '企业全局'), ('business', '业务与经营')):
        if data.get(key):
            section(key, title, notes(data[key]))
    if data.get('timeline'):
        body = '<div class="timeline">' + ''.join(f'<div><strong>{esc(x["year"])}</strong><article><h3>{esc(x["title"])}</h3><p>{para(x["text"])}</p>{citations(x["refs"])}</article></div>' for x in data['timeline']) + '</div>'
        section('timeline', '年度时间线', body)
    if projects:
        def select(field, label):
            options = ''.join(f'<option value="{esc(x)}">{esc(x)}</option>' for x in sorted({p[field] for p in projects.values()}))
            return f'<label>{label}<select id="{field}"><option value="">全部</option>{options}</select></label>'

        cards = []
        for pid, p in projects.items():
            parent = p.get('parent_id')
            rel = f'<p class="note">母项：<a href="#project-{esc(parent)}">{esc(projects[parent]["title"])}</a></p>' if parent else ''
            warning = f'<p class="caution"><b>引用边界：</b>{para(p["caution"])}</p>' if p.get('caution') else ''
            meaning = f'<p><b>作用与岗位理解 <span class="badge">分析</span></b><br>{para(p["meaning"])}</p>' if p.get('meaning') else ''
            policy = f'<p><b>政策／战略关联</b> <span class="badge">{esc(p.get("policy_basis", "未标关系类型"))}</span><br>{para(p["policy"])}<br>{citations(p.get("policy_refs", []))}</p>' if p.get('policy') else ''
            dates = '；'.join(f'{s}：{sources[s]["date"]}／{sources[s]["access"]}' for s in p['refs'])
            cards.append(f'<article class="project" id="project-{esc(pid)}" data-year="{esc(p["year"])}" data-kind="{esc(p["kind"])}" data-status="{esc(p["status"])}" data-priority="{str(p.get("priority", False)).lower()}"><div class="card-top"><span>{esc(pid)}</span><span class="badge">{esc(p["status"])}</span>{"<span class=focus>重点复习</span>" if p.get("priority") else ""}</div><h3>{esc(p["title"])}</h3><p class="meta">{esc(p["year"])} · {esc(p["region"])} · {esc(p["kind"])}</p><p class="note"><b>归属／角色：</b>{para(p["owner"])}</p>{rel}<div class="fact"><b>公开事实</b><p>{para(p["fact"])}</p></div>{meaning}{policy}{warning}<div class="source-line">{citations(p["refs"])}<small>{esc(dates)}</small></div></article>')
        filters = '<div class="filters"><label class="search">搜索项目、地区、技术或政策<input type="search" id="search" placeholder="输入关键词，可用空格组合" autocomplete="off"></label>' + select('year', '年份') + select('kind', '类型') + select('status', '状态') + '<label class="check"><input type="checkbox" id="priority">只看重点</label><button id="reset">重置</button></div>'
        section('projects', '项目与建设行动', f'<p>年份为事件或已知来源标签，精确含义见卡片。事实引用附原文，分析不等同于企业原话。</p>{filters}<p id="results" aria-live="polite">显示 {len(cards)} / {len(cards)} 个卡片</p><div class="grid projects">{"".join(cards)}</div><p id="empty" hidden>没有匹配项，请缩短关键词或重置。</p>')
        grouped = {}
        for pid, p in projects.items():
            grouped.setdefault(p['region'], []).append((pid, p['title']))
        body = '<div class="table-wrap"><table><thead><tr><th>地区／业务场景</th><th>案例索引</th></tr></thead><tbody>' + ''.join(f'<tr><td>{esc(region)}</td><td>' + '；'.join(f'<a href="#project-{esc(pid)}">{esc(title)}</a>' for pid, title in entries) + '</td></tr>' for region, entries in grouped.items()) + '</tbody></table></div>'
        section('regions', '地区与场景索引', body)
    for key, title in (('policies', '政策与战略对应'), ('outlook', '未来规划与趋势')):
        if data.get(key):
            section(key, title, notes(data[key]))
    if data.get('interviews'):
        body = '<p class="note">回答框架和练习问法，不代表实际招聘题库。个人经历只补入真实材料。</p>' + ''.join(f'<details><summary>{esc(x["question"])}<small>{esc(x.get("angle", "学习框架"))}</small></summary><div><p>{para(x["answer"])}</p><p class="note">{para(x.get("followup", ""))}</p>{citations(x.get("refs", []))}</div></details>' for x in data['interviews'])
        section('interviews', '岗位理解与面试框架', body)
    if data.get('clues'):
        section('clues', '补充线索与待核事项', notes(data['clues']))
    if data.get('coverage'):
        body = '<div class="table-wrap"><table><thead><tr><th>维度</th><th>覆盖程度</th><th>证据与缺口</th></tr></thead><tbody>' + ''.join(f'<tr><td>{esc(x["dimension"])}</td><td>{esc(x["status"])}</td><td>{para(x["detail"])}<br>{citations(x.get("refs", []))}</td></tr>' for x in data['coverage']) + '</tbody></table></div>'
        section('coverage', '覆盖检查与检索缺口', body)
    source_rows = ''.join(f'<tr id="source-{esc(sid)}"><td>{esc(sid)}</td><td><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a></td><td>{esc(s["date"])}</td><td>{esc(s["level"])}<br>{esc(s["access"])}<small>{para(s.get("note", ""))}</small></td></tr>' for sid, s in sources.items())
    section('sources', '来源目录', '<div class="table-wrap"><table><thead><tr><th>编号</th><th>标题与原文</th><th>日期／期间</th><th>层次与访问范围</th></tr></thead><tbody>' + source_rows + '</tbody></table></div>')
    title = meta.get('title', f'{meta["company"]}面试研究手册')
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head><body><aside><b>{esc(meta["company"])}</b><small>企业面试全景调研</small><nav>{"".join(nav)}</nav><p>截止 {esc(meta["cutoff"])}<br>离线可读 · 原文需联网</p></aside><main id="top"><header><span class="eyebrow">COMPANY · PROJECTS · OUTLOOK</span><h1>{esc(meta["company"])}<br>业务、项目与未来规划</h1><p>{esc(meta["period"])}</p><div class="actions"><button id="print">打印／保存PDF</button><button id="expand">展开面试问答</button></div></header><div class="stats"><div><b>{len(projects)}</b>项目／行动卡片</div><div><b>{len(sources)}</b>来源</div><div><b>{len(data.get("interviews", []))}</b>练习问法</div></div>{"".join(sections)}<footer>公开资料整理 · 截止 {esc(meta["cutoff"])}。事实、计划、预测与分析请按标签及来源阅读。<br>卡片数量不代表公司全部独立项目。自包含HTML，无外部脚本或字体依赖。</footer></main><a class="back" href="#top">回到顶部 ↑</a><script>{JS}</script></body></html>'


CSS = '''*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:#f4f5f0;color:#263d33;font:16px/1.8 "Microsoft YaHei","Segoe UI",sans-serif}a{color:#16745a;text-decoration:none}a:hover{text-decoration:underline}button,input,select{font:inherit}button{cursor:pointer;padding:7px 14px;border:1px solid #c4d1c3;border-radius:7px;background:white;color:#254c3b}aside{position:fixed;left:0;top:0;bottom:0;width:238px;background:#16352f;color:#dceadd;padding:28px 20px;overflow:auto}aside b{font-size:18px}aside small{display:block;color:#b9ccbd;font-size:12px;margin-top:5px}aside nav{margin-top:25px}aside a{display:block;color:#d0dfd1;padding:6px 8px;font-size:14px}aside p{font-size:12px;color:#a9bcab;margin-top:25px}main{margin-left:238px;padding:35px 45px;max-width:1540px}header{background:#1b483c;color:#f6f5e9;border-radius:16px;padding:36px 40px}header p{color:#cee0cc}.eyebrow{font-size:11px;color:#ddbb72;letter-spacing:3px}h1{font-size:36px;line-height:1.45;margin:16px 0}h2{font-size:26px;color:#234d38;margin:0 0 18px}h3{font-size:19px;line-height:1.6;margin:10px 0}p{margin:10px 0 16px}.actions{display:flex;gap:10px;flex-wrap:wrap}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0 30px}.stats>div{background:white;border:1px solid #dce5d7;padding:15px 20px;border-radius:10px;font-size:12px}.stats b{display:block;font-size:28px;color:#2e6b48}section{padding:30px 0;border-bottom:1px solid #dce3d6}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}article{background:white;padding:24px;border:1px solid #dce5d7;border-radius:12px}article p{font-size:14px}article b{font-size:12px}.badge{font-size:10px;background:#eaf0e2;color:#52734a;border-radius:15px;padding:3px 8px}.card-top{display:flex;gap:8px;align-items:center;font-size:11px;color:#78866f}.focus{font-size:10px;color:#a27b30;background:#f8efd9;padding:2px 7px;border-radius:15px}.meta,.note{font-size:12px;color:#71816d}.fact{background:#f1f5eb;padding:12px 14px;border-radius:8px}.fact p{margin:5px 0 0}.caution,.callout{background:#faf2df;border-left:3px solid #c19b50;padding:13px 18px;border-radius:0 8px 8px 0;font-size:12px}.callout{font-size:14px}.source-line{border-top:1px solid #e5ebdf;padding-top:12px}.cite{display:inline-block;font-size:11px;margin:2px 7px 2px 0}small{display:block;font-size:10px;color:#83907b}.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:end;background:#e9efe3;padding:18px;border-radius:10px}.filters label{display:flex;flex-direction:column;font-size:12px;gap:5px}.search{flex:1;min-width:230px}input[type=search],select{height:40px;padding:5px 10px;border:1px solid #bdcbb7;border-radius:6px;background:white;color:#314e3a}.check{flex-direction:row!important;align-items:center;height:40px}#results,#empty{font-size:12px;color:#6f8267}.timeline>div{display:grid;grid-template-columns:95px 1fr;gap:20px;margin:15px 0}.timeline strong{font-size:24px;color:#467b53}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th{text-align:left;background:#e7eee2;padding:12px 15px;white-space:nowrap}td{padding:13px 15px;vertical-align:top;border-bottom:1px solid #e5ebdf;min-width:100px}details{background:white;border:1px solid #dce5d7;border-radius:9px;margin:12px 0}summary{cursor:pointer;padding:16px 20px;font-weight:600}summary small{font-weight:normal}details>div{padding:0 22px 12px}footer{font-size:12px;color:#819177;padding:30px 0}.back{position:fixed;right:20px;bottom:20px;background:white;border:1px solid #c6d5bd;border-radius:7px;padding:6px 10px;font-size:12px}[hidden]{display:none!important}:focus-visible{outline:2px solid #c4a15b;outline-offset:2px}@media(max-width:1080px){main{padding:28px}.grid{grid-template-columns:1fr}}@media(max-width:750px){aside{position:relative;width:auto;padding:14px 20px}aside nav{display:flex;overflow-x:auto;gap:10px;margin-top:12px}aside a{white-space:nowrap;font-size:12px}aside p{display:none}main{margin:0;padding:18px 15px}header{padding:26px}h1{font-size:28px}.stats{gap:8px}.stats>div{padding:12px;font-size:10px}.stats b{font-size:24px}.timeline>div{grid-template-columns:65px 1fr;gap:10px}}@media print{aside,.actions,.filters,.back,#results,#empty{display:none!important}main{margin:0;padding:0;max-width:none}body{background:white;font-size:11pt}header{background:white;color:#28452e;padding:12px 0}header p,.eyebrow{color:#6d7c63}h1{font-size:24pt}h2{font-size:18pt}.grid{display:block}article,details{break-inside:avoid;margin:10px 0;padding:15px}.project[hidden]{display:block!important}.table-wrap{overflow:visible}table{font-size:9pt}.timeline>div{break-inside:avoid}.cite{font-size:8pt}a{color:#3c6640}}'''

JS = '''const cards=[...document.querySelectorAll('.project')];const ids=['search','year','kind','status','priority'];const controls=ids.map(x=>document.getElementById(x));
function filter(){if(!cards.length)return;const [q,y,k,s,p]=controls;const words=q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);let count=0;cards.forEach(c=>{const show=words.every(w=>c.textContent.toLowerCase().includes(w))&&(!y.value||c.dataset.year===y.value)&&(!k.value||c.dataset.kind===k.value)&&(!s.value||c.dataset.status===s.value)&&(!p.checked||c.dataset.priority==='true');c.hidden=!show;if(show)count++});document.getElementById('results').textContent=`显示 ${count} / ${cards.length} 个卡片`;document.getElementById('empty').hidden=count>0}
controls.filter(Boolean).forEach(c=>c.addEventListener(c.type==='search'?'input':'change',filter));document.getElementById('reset')?.addEventListener('click',()=>{controls.forEach(c=>c.type==='checkbox'?c.checked=false:c.value='');filter()});
const details=[...document.querySelectorAll('details')];document.getElementById('expand').disabled=!details.length;document.getElementById('expand').addEventListener('click',()=>{const open=details.some(d=>!d.open);details.forEach(d=>d.open=open);document.getElementById('expand').textContent=open?'收起面试问答':'展开面试问答'});document.getElementById('print').addEventListener('click',()=>window.print());
const parents=new Map(cards.map(c=>[c.id,c]));document.querySelectorAll('a[href^="#project-"]').forEach(a=>a.addEventListener('click',()=>{const target=parents.get(a.getAttribute('href').slice(1));if(target){target.hidden=false;document.getElementById('results').textContent=`显示 ${cards.filter(c=>!c.hidden).length} / ${cards.length} 个卡片`;document.getElementById('empty').hidden=true}}));
window.addEventListener('beforeprint',()=>details.forEach(d=>{d.dataset.wasOpen=String(d.open);d.open=true}));window.addEventListener('afterprint',()=>details.forEach(d=>d.open=d.dataset.wasOpen==='true'));'''


def csv_value(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    text = '' if value is None else str(value)
    # Source text is untrusted; protect spreadsheet readers from formula prefixes.
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        text = "'" + text
    return text


def export_csv(path, records, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in fields} for row in records)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('--out-dir', type=Path)
    ap.add_argument('--validate-only', action='store_true')
    ap.add_argument('--overwrite', action='store_true')
    args = ap.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8-sig'))
        sources, projects = validate(data)
        if args.validate_only:
            print(json.dumps({'valid': True, 'sources': len(sources), 'projects': len(projects)}, ensure_ascii=False))
            return 0
        if args.out_dir is None:
            ap.error('渲染需要 --out-dir；或使用 --validate-only')
        out = args.out_dir.resolve()
        skill_root = Path(__file__).resolve().parent.parent
        if out == skill_root or skill_root in out.parents:
            raise ValueError('报告目录不能放在技能目录内')
        existing = [name for name in FILES if (out / name).exists()]
        if existing and not args.overwrite:
            raise ValueError(f'已有生成文件：{existing}；请用新目录或有意更新时加 --overwrite')
        page = render(data, sources, projects)
        out.mkdir(parents=True, exist_ok=True)
        (out / FILES[0]).write_text(page, encoding='utf-8')
        (out / FILES[1]).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        export_csv(out / FILES[2], list(sources.values()), ('id', 'title', 'url', 'date', 'level', 'access', 'note'))
        export_csv(out / FILES[3], list(projects.values()), ('id', 'title', 'year', 'region', 'kind', 'status', 'owner', 'parent_id', 'fact', 'refs', 'meaning', 'policy', 'policy_basis', 'policy_refs', 'caution', 'priority'))
        print(json.dumps({'html': str(out / FILES[0]), 'sources': len(sources), 'projects': len(projects)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
