# 调研 JSON 契约

渲染器不联网搜集、不判断真实性、不升级项目阶段。UTF-8 JSON，Python 3.10+标准库。

## 顶层

必填meta和非空sources，其余数组按内容使用。全面调研应补充适用维度，不能因为可空就跳过研究。

```json
{
  "meta": {
    "company": "目标公司全称",
    "entity": "集团及本次主体边界",
    "cutoff": "2026-10-05",
    "period": "2021—2025及2026已公开进展",
    "role": "岗位未知，先按通用面试整理",
    "title": "企业面试研究手册",
    "scope": "范围与方法",
    "limitations": ["具体的覆盖缺口"]
  },
  "sources": [],
  "overview": [],
  "business": [],
  "timeline": [],
  "projects": [],
  "policies": [],
  "outlook": [],
  "interviews": [],
  "coverage": [],
  "clues": []
}
```

meta必填company、cutoff、period、scope、limitations。cutoff从会话取得，格式YYYY-MM-DD；不要复制示例日期。晚于截止的披露不算当日已知事实。

## 来源 sources

每项：`{id,title,url,date,level,access,note}`；除note外必填。url为真正读取的HTTP(S)原文地址。date为真实日期或可见期间，不虚构；level标企业公告、政府文件、报告、媒体或转载等；access标全文、部分正文、检索摘要、附件已解析或仅线索。id供交叉引用，HTML给标题和原文链接。

## 项目 projects

```json
{
  "id": "P01",
  "title": "项目名及核实别名",
  "year": "2026",
  "region": "地区或业务场景",
  "kind": "适合行业的项目类型",
  "status": "来源支持的准确阶段",
  "owner": "目标公司角色及其他业主边界",
  "parent_id": "可选：母项ID",
  "fact": "做什么、数字、日期、已知最新阶段",
  "refs": ["S01"],
  "meaning": "作用解释与岗位理解（分析）",
  "policy": "政策关系说明或未查到直接依据",
  "policy_basis": "直接依据／明确关联／方向关联（分析）／未核实",
  "policy_refs": ["S02"],
  "caution": "母子项、口径或状态边界",
  "priority": true
}
```

必填id、title、year、region、kind、status、owner、fact、refs。year只作筛选，事件／报道年差异写fact或caution；未核实可填“未核实”。status按行业适配，包括已交付、试运行、实施中、招标／前期、规划／拟议、持续运营、已终止、未核实等。

子项、批次、分期在kind／caution注明；卡片数不是独立项目总数。直接政策关系须有policy_refs，其他分析标明确。不能用一组笼统来源遮盖未支持的多个事实。

## 其他数组

- overview、business、policies、outlook、clues：`{title,text,basis,refs}`。title/text/非空refs必填，basis可选为来源事实、正式政策、企业公开计划、政府正式规划、趋势分析、待核验线索。趋势分析也要有支撑资料，但不冒充来源原话。
- timeline：`{year,title,text,refs}`，均必填，代表性节点而非完整清单。
- interviews：`{question,angle,answer,followup,refs}`；question/answer必填，refs可空，普通框架是分析。企业事实附refs，不能编个人经历或真实考题。
- coverage：`{dimension,status,detail,refs}`；前三项必填，status为已覆盖、部分覆盖、未查得、不适用，refs可空。记录真实覆盖及缺口。

字段只写纯文本，不塞HTML／脚本／Markdown；链接通过sources生成。

## CLI

```text
python scripts/render_dossier.py research.json --validate-only
python scripts/render_dossier.py research.json --out-dir <新版本目录>
python scripts/render_dossier.py research.json --out-dir <既有交付目录> --overwrite
```

输出：企业面试研究手册.html、资料数据.json、来源目录.csv、项目卡片.csv。CSV为UTF-8 BOM，并避免将来源文本前缀作为表格公式解释。默认保护已有生成文件，--overwrite仅用于有意重建。

校验字段、引用、编号、母子项和循环、链接、布尔值及日期格式。结构成功不代表事实正确或覆盖完整；仍核原文和浏览器行为。
