# 企业面试全景调研 Skill

`company-interview-research` 为求职面试调研目标企业的业务、近年项目、政策背景、未来规划和岗位要求，生成带来源的可搜索 HTML 资料。

## 安装与使用

将 `company-interview-research` 文件夹复制到 Codex skills 目录（通常为 `~/.codex/skills/`），重新加载技能。

```text
$company-interview-research 我要应聘某公司的某岗位，请调研近五年业务、项目、政策及未来规划，做成详细 HTML。
```

可提供招聘链接、公司全称、岗位、地区和时间范围。技能会核对集团与子公司归属、项目阶段、来源时间及公开资料缺口。

## 文件与渲染

- `SKILL.md`：工作流程和核验要求。
- `agents/openai.yaml`：技能展示配置。
- `references/`：检索方法和数据格式。
- `scripts/render_dossier.py`：使用 Python 标准库生成离线 HTML、JSON 和 CSV。

```text
python company-interview-research/scripts/render_dossier.py research.json --validate-only
python company-interview-research/scripts/render_dossier.py research.json --out-dir output
```

公开资料不能保证穷尽企业内部项目；事实、计划、分析和待核验事项分别标注。本仓库只包含通用 skill，不包含个人简历、企业调研报告或下载的第三方资料。
